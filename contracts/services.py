from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .fields import HalfUpDecimalField


def get_current_expiry(contract, effective_date, extra_endorsement=None):
    expiry = contract.expiry_date
    extensions = list(contract.endorsements.filter(
        status="AGREED",
        type="EXTENSION",
        effective_date__lte=effective_date,
    ).values("endorsement_number", "changes"))

    if (
        extra_endorsement
        and extra_endorsement["type"] == "EXTENSION"
        and extra_endorsement["effective_date"] <= effective_date
    ):
        extensions.append(extra_endorsement)

    for extension in sorted(extensions, key=lambda item: item["endorsement_number"]):
        expiry = date.fromisoformat(extension["changes"]["expiry_date"])

    return expiry


def validate_endorsement_number(contract, endorsement_number):
    if contract.endorsements.filter(
        endorsement_number=endorsement_number
    ).exists():
        raise ValidationError({
            "endorsement_number": "This number is already used for this contract."
        })


def validate_effective_date(contract, effective_date):
    cancelled = contract.endorsements.filter(
        status="AGREED",
        type="CANCELLATION",
        effective_date__lte=effective_date,
    ).exists()

    if cancelled:
        raise ValidationError({
            "effective_date": "Cannot take effect on or after cancellation."
        })

    current_expiry = get_current_expiry(contract, effective_date)
    if not contract.inception_date <= effective_date <= current_expiry:
        raise ValidationError({
            "effective_date": "Must fall within the current cover period."
        })


def validate_extension(contract, effective_date, changes):
    try:
        new_expiry = date.fromisoformat(changes["expiry_date"])
    except (KeyError, TypeError, ValueError):
        raise ValidationError({
            "changes": {
                "expiry_date": "Provide a valid date in YYYY-MM-DD format."
            }
        })

    current_expiry = get_current_expiry(contract, effective_date)
    if new_expiry <= current_expiry:
        raise ValidationError({
            "changes": {
                "expiry_date": "Must be later than the current expiry date."
            }
        })


def validate_premium(contract, data):
    # Call with serializer.validated_data, after calculating any cancellation refund.
    if data["premium_change"] is None:
        raise ValidationError({
            "premium_change": "Provide an amount or calculate the cancellation refund first."
        })

    if data["status"] == "DRAFT":
        return

    endorsements = list(contract.endorsements.filter(status="AGREED").values(
        "endorsement_number", "effective_date", "premium_change"
    ))
    endorsements.append(data)
    endorsements.sort(key=lambda item: item["endorsement_number"])

    # Balances can change only on effective dates. Check every such position.
    dates = sorted({item["effective_date"] for item in endorsements})
    for as_at in dates:
        gross = contract.gross_premium
        for item in endorsements:
            if item["effective_date"] <= as_at:
                gross += item["premium_change"]
                if gross < 0:
                    raise ValidationError({
                        "premium_change": "Gross premium cannot become negative."
                    })


def calculate_cancellation_premium(contract, effective_date, extra_endorsement=None):
    expiry = get_current_expiry(contract, effective_date, extra_endorsement)
    gross = contract.gross_premium

    endorsements = contract.endorsements.filter(
        status="AGREED",
        effective_date__lte=effective_date,
    ).exclude(type="CANCELLATION")

    for endorsement in endorsements:
        gross += endorsement.premium_change

    if extra_endorsement and extra_endorsement["effective_date"] <= effective_date:
        gross += extra_endorsement["premium_change"]

    total_days = (expiry - contract.inception_date).days + 1
    unused_days = (expiry - effective_date).days + 1
    refund = gross * Decimal(unused_days) / Decimal(total_days)

    return (-refund).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_changes(contract, data):
    changes = data.get("changes", {})
    if not isinstance(changes, dict):
        raise ValidationError({"changes": "Must be a JSON object."})

    fields = {
        "CHANGE_SUM_INSURED": {
            "sum_insured": HalfUpDecimalField(
                max_digits=18, decimal_places=2, min_value=Decimal("0.00")
            )
        },
        "CHANGE_DETAILS": {"insured_name": serializers.CharField(max_length=255)},
        "EXTENSION": {"expiry_date": serializers.DateField()},
        "PREMIUM_ADJUSTMENT": {},
        "CANCELLATION": {},
    }[data["type"]]

    if set(changes) != set(fields):
        expected = ", ".join(fields) or "no fields"
        raise ValidationError({"changes": f"Expected {expected} for this type."})

    cleaned = {}
    for name, field in fields.items():
        try:
            value = field.run_validation(changes[name])
        except ValidationError as error:
            raise ValidationError({"changes": {name: error.detail}})
        cleaned[name] = str(value)

    data["changes"] = cleaned
    if data["type"] == "EXTENSION":
        validate_extension(contract, data["effective_date"], cleaned)


def validate_endorsement(contract, data):
    validate_endorsement_number(contract, data["endorsement_number"])
    validate_effective_date(contract, data["effective_date"])
    validate_changes(contract, data)

    if data["type"] == "CANCELLATION":
        if contract.endorsements.filter(
            status="AGREED", effective_date__gte=data["effective_date"]
        ).exists():
            raise ValidationError({
                "effective_date": "Cancellation conflicts with existing agreed endorsements."
            })
        data["premium_change"] = calculate_cancellation_premium(
            contract, data["effective_date"]
        )
        data["premium_change"] = HalfUpDecimalField(
            max_digits=18, decimal_places=2
        ).run_validation(data["premium_change"])

    validate_premium(contract, data)

    if data["status"] == "AGREED":
        cancellations = contract.endorsements.filter(status="AGREED", type="CANCELLATION")
        for cancellation in cancellations:
            refund = calculate_cancellation_premium(
                contract, cancellation.effective_date, extra_endorsement=data
            )
            if refund != cancellation.premium_change:
                raise ValidationError({
                    "effective_date": "This backdated change would alter a stored cancellation refund."
                })

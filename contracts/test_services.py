from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .models import Contract, Endorsement
from .services import calculate_cancellation_premium, validate_premium


class PremiumValidationTests(TestCase):
    def setUp(self):
        self.contract = Contract.objects.create(
            mga_reference="PREMIUM-TEST",
            insured_name="Test Insured",
            class_of_business="Property",
            inception_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
            currency="GBP",
            sum_insured=Decimal("1000.00"),
            gross_premium=Decimal("100.00"),
            brokerage_pct=Decimal("20.00"),
            signed_line_pct=Decimal("25.00"),
        )

    def data(self, number=1, amount="-100.00", effective=date(2026, 3, 1), status="AGREED"):
        return {
            "endorsement_number": number,
            "type": "PREMIUM_ADJUSTMENT",
            "status": status,
            "effective_date": effective,
            "recorded_date": date(2026, 8, 1),
            "premium_change": Decimal(amount),
            "changes": {},
            "reason": "Test adjustment",
        }

    def test_return_can_reduce_premium_to_zero(self):
        validate_premium(self.contract, self.data())

    def test_excessive_return_is_rejected(self):
        with self.assertRaises(ValidationError) as error:
            validate_premium(self.contract, self.data(amount="-100.01"))
        self.assertIn("premium_change", error.exception.detail)

    def test_draft_return_does_not_affect_position(self):
        validate_premium(self.contract, self.data(amount="-200.00", status="DRAFT"))

    def test_stored_draft_increase_cannot_fund_agreed_return(self):
        Endorsement.objects.create(
            contract=self.contract, **self.data(amount="200.00", status="DRAFT")
        )
        with self.assertRaises(ValidationError):
            validate_premium(self.contract, self.data(number=2, amount="-150.00"))

    def test_future_increase_cannot_fund_backdated_return(self):
        Endorsement.objects.create(
            contract=self.contract,
            **self.data(amount="100.00", effective=date(2026, 7, 1)),
        )
        with self.assertRaises(ValidationError):
            validate_premium(self.contract, self.data(number=2, amount="-150.00"))

    def test_positive_final_total_cannot_hide_negative_intermediate_balance(self):
        Endorsement.objects.create(
            contract=self.contract, **self.data(number=2, amount="100.00")
        )
        with self.assertRaises(ValidationError):
            validate_premium(self.contract, self.data(number=1, amount="-150.00"))

    def test_null_premium_requires_calculation_before_validation(self):
        data = self.data()
        data["premium_change"] = None
        with self.assertRaises(ValidationError):
            validate_premium(self.contract, data)


class CancellationPremiumTests(TestCase):
    def create_contract(self, gross="120000.00", expiry=date(2026, 12, 31)):
        return Contract.objects.create(
            mga_reference="CANCELLATION-TEST",
            insured_name="Harbour Logistics Ltd",
            class_of_business="Property",
            inception_date=date(2026, 1, 1),
            expiry_date=expiry,
            currency="GBP",
            sum_insured=Decimal("5000000.00"),
            gross_premium=Decimal(gross),
            brokerage_pct=Decimal("20.00"),
            signed_line_pct=Decimal("25.00"),
        )

    def add_endorsement(self, contract, number, amount, effective, status="AGREED",
                        type="PREMIUM_ADJUSTMENT", changes=None):
        return Endorsement.objects.create(
            contract=contract,
            endorsement_number=number,
            type=type,
            status=status,
            effective_date=effective,
            recorded_date=date(2026, 10, 1),
            premium_change=Decimal(amount),
            changes=changes or {},
            reason="Test cancellation calculation",
        )

    def test_sample_refund_excludes_drafts_future_changes_and_cancellation(self):
        contract = self.create_contract()
        self.add_endorsement(contract, 1, "20000.00", date(2026, 3, 1))
        self.add_endorsement(contract, 2, "5000.00", date(2026, 6, 1), status="DRAFT")
        self.add_endorsement(contract, 3, "1000.00", date(2026, 10, 1))
        self.add_endorsement(contract, 4, "-35671.23", date(2026, 9, 30), type="CANCELLATION")

        refund = calculate_cancellation_premium(contract, date(2026, 9, 30))
        self.assertEqual(refund, Decimal("-35671.23"))
        contract.refresh_from_db()
        self.assertEqual(contract.gross_premium, Decimal("120000.00"))

    def test_cancellation_at_inception_returns_full_premium(self):
        contract = self.create_contract()
        self.assertEqual(
            calculate_cancellation_premium(contract, date(2026, 1, 1)),
            Decimal("-120000.00"),
        )

    def test_cancellation_at_expiry_returns_one_day(self):
        contract = self.create_contract()
        self.assertEqual(
            calculate_cancellation_premium(contract, date(2026, 12, 31)),
            Decimal("-328.77"),
        )

    def test_half_cent_rounds_up(self):
        contract = self.create_contract(gross="0.01", expiry=date(2026, 1, 2))
        self.assertEqual(
            calculate_cancellation_premium(contract, date(2026, 1, 2)),
            Decimal("-0.01"),
        )

    def test_extension_changes_days_and_gross_used_for_refund(self):
        contract = self.create_contract(gross="365.00")
        self.add_endorsement(
            contract, 1, "31.00", date(2026, 6, 1), type="EXTENSION",
            changes={"expiry_date": "2027-01-31"},
        )
        self.assertEqual(
            calculate_cancellation_premium(contract, date(2026, 12, 31)),
            Decimal("-32.00"),
        )

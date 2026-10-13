from django.db import models

class Contract(models.Model):
    mga_reference = models.CharField(max_length=100, unique=True)
    insured_name = models.CharField(max_length=255)
    class_of_business = models.CharField(max_length=100)
    inception_date = models.DateField()
    expiry_date = models.DateField()
    currency = models.CharField(max_length=3)
    sum_insured = models.DecimalField(max_digits=18, decimal_places=2)
    gross_premium = models.DecimalField(max_digits=18, decimal_places=2)
    brokerage_pct = models.DecimalField(max_digits=5, decimal_places=2)
    signed_line_pct = models.DecimalField(max_digits=5, decimal_places=2)

    status = models.CharField(
        max_length=10,
        default="BOUND",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.mga_reference


class Endorsement(models.Model):
    contract = models.ForeignKey(
        Contract,
        on_delete=models.PROTECT,
        related_name="endorsements",
    )

    endorsement_number = models.PositiveIntegerField()
    type = models.CharField(
        max_length=30,
        choices=[
            ("CHANGE_SUM_INSURED", "Change sum insured"),
            ("CHANGE_DETAILS", "Change details"),
            ("PREMIUM_ADJUSTMENT", "Premium adjustment"),
            ("EXTENSION", "Extension"),
            ("CANCELLATION", "Cancellation"),
        ],
    )
    status = models.CharField(
        max_length=10,
        choices=[("DRAFT", "Draft"), ("AGREED", "Agreed")],
    )

    effective_date = models.DateField()
    recorded_date = models.DateField()

    premium_change = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    changes = models.JSONField(default=dict)
    reason = models.TextField()

    class Meta:
        ordering = ["endorsement_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "endorsement_number"],
                name="unique_endorsement_number_per_contract",
            )
        ]

    def __str__(self):
        return f"{self.contract.mga_reference} - {self.endorsement_number}"

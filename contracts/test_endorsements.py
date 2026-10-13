from rest_framework.test import APITestCase

from .models import Contract, Endorsement


class EndorsementAPITests(APITestCase):
    def setUp(self):
        self.contract = Contract.objects.create(
            mga_reference="MNK-PR-2026-001",
            insured_name="Harbour Logistics Ltd",
            class_of_business="Property",
            inception_date="2026-01-01",
            expiry_date="2026-12-31",
            currency="GBP",
            sum_insured="5000000.00",
            gross_premium="120000.00",
            brokerage_pct="20.00",
            signed_line_pct="25.00",
        )
        self.url = "/api/contracts/MNK-PR-2026-001/endorsements/"
        self.payload = {
            "endorsement_number": 1,
            "type": "CHANGE_SUM_INSURED",
            "status": "AGREED",
            "effective_date": "2026-03-01",
            "recorded_date": "2026-03-05",
            "premium_change": "20000.00",
            "changes": {"sum_insured": "6000000.00"},
            "reason": "New warehouse",
        }

    def post(self, **overrides):
        return self.client.post(self.url, {**self.payload, **overrides}, format="json")

    def test_create_preserves_original_slip(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["contract"], self.contract.pk)
        self.assertEqual(response.data["premium_change"], "20000.00")
        self.assertEqual(Endorsement.objects.count(), 1)
        self.contract.refresh_from_db()
        self.assertEqual(str(self.contract.sum_insured), "5000000.00")
        self.assertEqual(str(self.contract.gross_premium), "120000.00")
        self.assertEqual(self.contract.status, "BOUND")

    def test_unknown_contract_returns_field_error(self):
        response = self.client.post(
            "/api/contracts/UNKNOWN/endorsements/", self.payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("mga_reference", response.data)

    def test_duplicate_number_returns_field_error(self):
        self.assertEqual(self.post().status_code, 201)
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertIn("endorsement_number", response.data)
        self.assertEqual(Endorsement.objects.count(), 1)

    def test_invalid_dates_are_rejected(self):
        for effective in ["2025-12-31", "2027-01-01", "bad-date"]:
            with self.subTest(effective=effective):
                response = self.post(effective_date=effective)
                self.assertEqual(response.status_code, 400)
                self.assertIn("effective_date", response.data)
        self.assertEqual(Endorsement.objects.count(), 0)

    def test_missing_and_invalid_changes_are_rejected(self):
        for changes in [{}, [], {"sum_insured": "-1.00"}, {"sum_insured": "abc"},
                        {"sum_insured": "10.00", "insured_name": "Extra"}]:
            with self.subTest(changes=changes):
                response = self.post(changes=changes)
                self.assertEqual(response.status_code, 400)
                self.assertIn("changes", response.data)

    def test_invalid_type_status_and_number(self):
        for field, value in [("type", "UNKNOWN"), ("status", "UNKNOWN"),
                             ("endorsement_number", 0)]:
            with self.subTest(field=field):
                response = self.post(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_details_can_be_backdated_relative_to_recording(self):
        response = self.post(
            type="CHANGE_DETAILS", premium_change="0.00",
            changes={"insured_name": "Harbour Logistics Group Ltd"},
            effective_date="2026-02-01", recorded_date="2026-04-10",
        )
        self.assertEqual(response.status_code, 201)

    def test_extension_enables_later_effective_date(self):
        response = self.post(type="EXTENSION", changes={"expiry_date": "2027-06-30"})
        self.assertEqual(response.status_code, 201)
        response = self.post(
            endorsement_number=2, effective_date="2027-02-01",
            type="PREMIUM_ADJUSTMENT", changes={},
        )
        self.assertEqual(response.status_code, 201)

    def test_invalid_extensions_are_rejected(self):
        for expiry in ["2026-12-31", "2026-11-30", "invalid"]:
            with self.subTest(expiry=expiry):
                response = self.post(type="EXTENSION", changes={"expiry_date": expiry})
                self.assertEqual(response.status_code, 400)
                self.assertIn("changes", response.data)

    def test_draft_extension_does_not_extend_cover(self):
        self.assertEqual(self.post(
            type="EXTENSION", status="DRAFT", changes={"expiry_date": "2027-06-30"}
        ).status_code, 201)
        response = self.post(endorsement_number=2, effective_date="2027-02-01")
        self.assertEqual(response.status_code, 400)

    def test_negative_premium_and_null_adjustment_are_rejected(self):
        for amount in ["-120000.01", None]:
            with self.subTest(amount=amount):
                response = self.post(
                    type="PREMIUM_ADJUSTMENT", changes={}, premium_change=amount
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("premium_change", response.data)

    def test_draft_does_not_fund_agreed_return(self):
        self.assertEqual(self.post(status="DRAFT").status_code, 201)
        response = self.post(
            endorsement_number=2, type="PREMIUM_ADJUSTMENT", changes={},
            premium_change="-130000.00",
        )
        self.assertEqual(response.status_code, 400)

    def test_cancellation_calculates_refund_and_blocks_later_changes(self):
        self.assertEqual(self.post().status_code, 201)
        response = self.post(
            endorsement_number=2, type="CANCELLATION", changes={},
            effective_date="2026-09-30", premium_change=None,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["premium_change"], "-35671.23")
        for effective in ["2026-09-30", "2026-10-05"]:
            with self.subTest(effective=effective):
                response = self.post(endorsement_number=3, effective_date=effective)
                self.assertEqual(response.status_code, 400)
                self.assertIn("effective_date", response.data)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "BOUND")
        self.assertEqual(str(self.contract.expiry_date), "2026-12-31")

    def test_cancellation_conflicting_with_existing_change_is_rejected(self):
        self.assertEqual(self.post(effective_date="2026-10-01").status_code, 201)
        response = self.post(
            endorsement_number=2, type="CANCELLATION", changes={},
            effective_date="2026-09-30", premium_change=None,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("effective_date", response.data)

    def test_backdated_change_cannot_silently_change_stored_refund(self):
        self.assertEqual(self.post(
            type="CANCELLATION", changes={}, effective_date="2026-09-30",
            premium_change=None,
        ).status_code, 201)
        response = self.post(endorsement_number=2)
        self.assertEqual(response.status_code, 400)
        self.assertIn("effective_date", response.data)
        # A zero-premium details change leaves the refund valid.
        response = self.post(
            endorsement_number=2, type="CHANGE_DETAILS", premium_change="0.00",
            changes={"insured_name": "Harbour Group"},
        )
        self.assertEqual(response.status_code, 201)

    def test_amounts_round_half_up(self):
        response = self.post(
            premium_change="0.005", changes={"sum_insured": "6000000.005"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["premium_change"], "0.01")
        self.assertEqual(response.data["changes"]["sum_insured"], "6000000.01")

    def test_invalid_and_oversized_amounts_return_400(self):
        for value in [0.1, "NaN", "Infinity", "10000000000000000.00"]:
            with self.subTest(value=value):
                response = self.post(premium_change=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("premium_change", response.data)

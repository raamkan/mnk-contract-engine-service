from datetime import date
from decimal import Decimal
from unittest.mock import patch

from rest_framework.test import APITestCase

from .models import Contract, Endorsement
from .services import calculate_position


class ContractDetailTests(APITestCase):
    def setUp(self):
        self.contract = Contract.objects.create(
            mga_reference="MNK-PR-2026-001",
            insured_name="Harbour Logistics Ltd",
            class_of_business="Property",
            inception_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
            currency="GBP",
            sum_insured=Decimal("5000000.00"),
            gross_premium=Decimal("120000.00"),
            brokerage_pct=Decimal("20.00"),
            signed_line_pct=Decimal("25.00"),
        )
        self.url = "/api/contracts/MNK-PR-2026-001/"

    def add(self, number, type, effective, premium="0.00", changes=None, status="AGREED"):
        return Endorsement.objects.create(
            contract=self.contract, endorsement_number=number, type=type,
            status=status, effective_date=effective, recorded_date=date(2027, 2, 14),
            premium_change=Decimal(premium), changes=changes or {}, reason="Test change",
        )

    @patch("contracts.services.timezone.localdate", return_value=date(2026, 10, 14))
    def test_detail_contains_slip_all_endorsements_and_current_position(self, today):
        self.add(1, "CHANGE_SUM_INSURED", date(2026, 3, 1), "20000.00",
                 {"sum_insured": "6000000.00"})
        self.add(2, "PREMIUM_ADJUSTMENT", date(2026, 6, 1), "5000.00", status="DRAFT")
        self.add(3, "CHANGE_DETAILS", date(2026, 11, 10),
                 changes={"insured_name": "Future Insured"})

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"slip", "endorsements", "current_position"})
        self.assertEqual(response.data["slip"]["sum_insured"], "5000000.00")
        self.assertEqual(len(response.data["endorsements"]), 3)
        position = response.data["current_position"]
        self.assertEqual(position, {
            "mga_reference": "MNK-PR-2026-001", "as_at": "2026-10-14",
            "insured_name": "Harbour Logistics Ltd", "status": "BOUND",
            "inception_date": "2026-01-01", "expiry_date": "2026-12-31",
            "cancellation_effective_date": None, "currency": "GBP",
            "sum_insured": "6000000.00", "gross_premium": "140000.00",
            "net_premium": "112000.00", "our_net_premium": "28000.00",
            "applied_endorsements": [1],
        })
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.sum_insured, Decimal("5000000.00"))
        self.assertEqual(self.contract.gross_premium, Decimal("120000.00"))

    def test_unknown_reference_returns_404(self):
        self.assertEqual(self.client.get("/api/contracts/UNKNOWN/").status_code, 404)

    def test_before_inception_returns_original_slip(self):
        self.add(1, "PREMIUM_ADJUSTMENT", date(2026, 1, 1), "100.00")
        position = calculate_position(self.contract, date(2025, 12, 31))
        self.assertEqual(position["applied_endorsements"], [])
        self.assertEqual(position["gross_premium"], "120000.00")
        self.assertEqual(position["status"], "BOUND")

    def test_number_order_takes_precedence_over_effective_order(self):
        self.add(1, "CHANGE_DETAILS", date(2026, 3, 1),
                 changes={"insured_name": "First change"})
        self.add(2, "CHANGE_DETAILS", date(2026, 2, 1),
                 changes={"insured_name": "Second change"})
        position = calculate_position(self.contract, date(2026, 3, 1))
        self.assertEqual(position["insured_name"], "Second change")
        self.assertEqual(position["applied_endorsements"], [1, 2])

    def test_effective_date_is_inclusive_and_recorded_date_does_not_filter(self):
        self.add(1, "PREMIUM_ADJUSTMENT", date(2026, 3, 1), "20000.00")
        before = calculate_position(self.contract, date(2026, 2, 28))
        on_date = calculate_position(self.contract, date(2026, 3, 1))
        self.assertEqual(before["applied_endorsements"], [])
        self.assertEqual(on_date["applied_endorsements"], [1])
        self.assertEqual(on_date["gross_premium"], "140000.00")

    def test_extension_changes_expiry_only_when_effective(self):
        self.add(1, "EXTENSION", date(2026, 10, 1), "11250.00",
                 {"expiry_date": "2027-06-30"})
        before = calculate_position(self.contract, date(2026, 9, 30))
        after = calculate_position(self.contract, date(2026, 10, 1))
        self.assertEqual(before["expiry_date"], "2026-12-31")
        self.assertEqual(after["expiry_date"], "2027-06-30")
        self.assertEqual(after["gross_premium"], "131250.00")

    @patch("contracts.services.timezone.localdate", return_value=date(2026, 10, 14))
    def test_cancelled_detail_keeps_original_slip_bound(self, today):
        self.add(1, "PREMIUM_ADJUSTMENT", date(2026, 3, 1), "20000.00")
        self.add(2, "CANCELLATION", date(2026, 9, 30), "-35671.23")
        before = calculate_position(self.contract, date(2026, 9, 29))
        self.assertEqual(before["status"], "BOUND")
        response = self.client.get(self.url)
        position = response.data["current_position"]
        self.assertEqual(position["status"], "CANCELLED")
        self.assertEqual(position["expiry_date"], "2026-09-29")
        self.assertEqual(position["cancellation_effective_date"], "2026-09-30")
        self.assertEqual(position["gross_premium"], "104328.77")
        self.assertEqual(position["net_premium"], "83463.02")
        self.assertEqual(position["our_net_premium"], "20865.76")
        self.assertEqual(response.data["slip"]["status"], "BOUND")
        self.assertEqual(response.data["slip"]["expiry_date"], "2026-12-31")

    def test_net_figures_round_half_up(self):
        # Unsaved values exercise a half-cent without changing the stored slip.
        self.contract.gross_premium = Decimal("0.01")
        self.contract.brokerage_pct = Decimal("50.00")
        self.contract.signed_line_pct = Decimal("50.00")
        position = calculate_position(self.contract, date(2026, 1, 1))
        self.assertEqual(position["net_premium"], "0.01")
        self.assertEqual(position["our_net_premium"], "0.01")

    def test_expiry_alone_does_not_cancel_contract(self):
        position = calculate_position(self.contract, date(2027, 1, 1))
        self.assertEqual(position["status"], "BOUND")
        self.assertIsNone(position["cancellation_effective_date"])

    def test_position_endpoint_filters_by_requested_date(self):
        self.add(1, "PREMIUM_ADJUSTMENT", date(2026, 3, 1), "20000.00")
        before = self.client.get(self.url + "position/", {"as_at": "2026-02-28"})
        on_date = self.client.get(self.url + "position/", {"as_at": "2026-03-01"})
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.data["as_at"], "2026-02-28")
        self.assertEqual(before.data["gross_premium"], "120000.00")
        self.assertEqual(before.data["applied_endorsements"], [])
        self.assertEqual(on_date.status_code, 200)
        self.assertEqual(on_date.data["gross_premium"], "140000.00")
        self.assertEqual(on_date.data["applied_endorsements"], [1])

    @patch("contracts.services.timezone.localdate", return_value=date(2026, 10, 14))
    def test_position_endpoint_defaults_to_today_and_matches_detail(self, today):
        response = self.client.get(self.url + "position/")
        detail = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["as_at"], "2026-10-14")
        self.assertEqual(response.data, detail.data["current_position"])

    def test_position_endpoint_rejects_invalid_dates(self):
        for value in ["", "bad-date", "2026-02-30", "2026-2-1", "20261014",
                      "2026-10-14T00:00:00", "2026-W42-3"]:
            with self.subTest(value=value):
                response = self.client.get(self.url + "position/", {"as_at": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("as_at", response.data)

    def test_position_endpoint_unknown_reference_returns_404(self):
        response = self.client.get("/api/contracts/UNKNOWN/position/")
        self.assertEqual(response.status_code, 404)

    def test_position_endpoint_before_inception_returns_slip(self):
        self.add(1, "PREMIUM_ADJUSTMENT", date(2026, 1, 1), "20000.00")
        response = self.client.get(self.url + "position/", {"as_at": "2025-12-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["applied_endorsements"], [])
        self.assertEqual(response.data["gross_premium"], "120000.00")

    def test_position_endpoint_get_only(self):
        response = self.client.post(self.url + "position/", {}, format="json")
        self.assertEqual(response.status_code, 405)

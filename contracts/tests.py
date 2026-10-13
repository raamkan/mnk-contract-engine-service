from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from .models import Contract


class ContractCreateTests(APITestCase):
    def setUp(self):
        self.payload = {
            "mga_reference": "MNK-PR-2026-001",
            "insured_name": "Harbour Logistics Ltd",
            "class_of_business": "Property",
            "inception_date": "2026-01-01",
            "expiry_date": "2026-12-31",
            "currency": "GBP",
            "sum_insured": "5000000.00",
            "gross_premium": "120000.00",
            "brokerage_pct": "20.00",
            "signed_line_pct": "25.00",
        }

    def test_create_contract(self):
        response = self.client.post("/api/contracts/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "BOUND")
        self.assertEqual(response.data["gross_premium"], "120000.00")
        self.assertTrue(Contract.objects.filter(
            mga_reference=self.payload["mga_reference"]
        ).exists())

    def test_missing_field(self):
        del self.payload["insured_name"]
        response = self.client.post("/api/contracts/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("insured_name", response.data)
        self.assertEqual(Contract.objects.count(), 0)

    def test_duplicate_reference(self):
        self.client.post("/api/contracts/", self.payload, format="json")
        response = self.client.post("/api/contracts/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("mga_reference", response.data)
        self.assertEqual(Contract.objects.count(), 1)


class HealthTests(SimpleTestCase):
    @patch("contracts.views.connection")
    def test_healthy_database(self, connection):
        connection.vendor = "postgresql"
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "postgresql")
        connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
            "SELECT 1"
        )

    @patch("contracts.views.connection")
    def test_unavailable_database(self, connection):
        connection.vendor = "postgresql"
        connection.cursor.side_effect = OperationalError("secret")
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertNotIn("secret", response.content.decode())

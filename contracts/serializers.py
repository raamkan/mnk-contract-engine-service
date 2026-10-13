from rest_framework import serializers
from django.db import models

from .fields import HalfUpDecimalField
from .models import Contract, Endorsement

class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = "__all__"
        read_only_fields = ["id", "status", "created_at"]


class EndorsementSerializer(serializers.ModelSerializer):
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.DecimalField: HalfUpDecimalField,
    }

    class Meta:
        model = Endorsement
        fields = "__all__"
        read_only_fields = ["id", "contract"]
        extra_kwargs = {
            "premium_change": {"allow_null": True},
            "endorsement_number": {"min_value": 1},
        }

from django.db import DatabaseError, connection, transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Contract
from .serializers import ContractSerializer, EndorsementSerializer
from .services import validate_endorsement


@api_view(["GET", "POST"])
def contracts(request):
    if request.method == "GET":
        slips = Contract.objects.all().order_by("mga_reference")
        serializer = ContractSerializer(slips, many=True)
        return Response(serializer.data)

    serializer = ContractSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def add_endorsement(request, mga_reference):
    with transaction.atomic():
        try:
            contract = Contract.objects.select_for_update().get(mga_reference=mga_reference)
        except Contract.DoesNotExist:
            raise ValidationError({"mga_reference": "Contract does not exist."})

        serializer = EndorsementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validate_endorsement(contract, serializer.validated_data)
        serializer.save(contract=contract)

    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def health(request, *args, **kwargs):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return Response(
            {
                "status": "error",
                "application": "mnk-contract-engine-service",
                "version": "1.0.0",
                "database": connection.vendor,
            },
            status=503,
        )

    return Response(
        {
            "status": "ok",
            "application": "mnk-contract-engine-service",
            "version": "1.0.0",
            "database": connection.vendor,
        }
    )





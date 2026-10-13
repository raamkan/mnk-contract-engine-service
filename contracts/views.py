from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Contract
from .serializers import ContractSerializer


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





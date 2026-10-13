from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request, *args, **kwargs):
    return Response(
        {
            "status": "ok",
            "application": "mnk-contract-engine-service",
            "version": "1.0.0",
        }
    )






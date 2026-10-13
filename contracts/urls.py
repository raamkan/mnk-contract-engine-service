from django.urls import path

from .views import add_endorsement, contract_detail, contract_position, contracts


urlpatterns = [
    path("contracts/", contracts, name="contract-create"),
    path(
        "contracts/<str:mga_reference>/",
        contract_detail,
        name="contract-detail",
    ),
    path(
        "contracts/<str:mga_reference>/position/",
        contract_position,
        name="contract-position",
    ),
    path(
        "contracts/<str:mga_reference>/endorsements/",
        add_endorsement,
        name="endorsement-create",
    ),
]


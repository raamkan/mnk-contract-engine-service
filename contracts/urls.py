from django.urls import path

from .views import add_endorsement, contracts


urlpatterns = [
    path("contracts/", contracts, name="contract-create"),
    path(
        "contracts/<str:mga_reference>/endorsements/",
        add_endorsement,
        name="endorsement-create",
    ),
]


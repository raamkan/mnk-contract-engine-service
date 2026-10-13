from django.urls import path

from .views import create_contract


urlpatterns = [
    path("contracts/", create_contract, name="contract-create"),
]


from django.urls import path

from .views import contracts


urlpatterns = [
    path("contracts/", contracts, name="contract-create"),
]


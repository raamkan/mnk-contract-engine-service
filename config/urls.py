from django.urls import include, path
from contracts.views import health

urlpatterns = [
    path("health/", health),
    path("api/", include("contracts.urls")),
]

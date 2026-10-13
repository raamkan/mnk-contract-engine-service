from django.urls import path
from contracts.views import health

urlpatterns = [
    path("health/", health),
]

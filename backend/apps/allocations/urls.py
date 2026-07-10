"""URL configuration for ``/api/v1/allocations/``."""
from rest_framework.routers import DefaultRouter

from .views import AllocationRunViewSet, AllocationViewSet, ConflictViewSet

router = DefaultRouter()
router.register(r"allocations", AllocationViewSet, basename="allocation")
router.register(r"runs", AllocationRunViewSet, basename="allocation-run")
router.register(r"conflicts", ConflictViewSet, basename="conflict")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import AvailabilityViewSet, InvigilatorProfileViewSet

router = DefaultRouter()
router.register(r"profiles", InvigilatorProfileViewSet, basename="invigilator-profile")
router.register(r"availability", AvailabilityViewSet, basename="availability")

urlpatterns = router.urls

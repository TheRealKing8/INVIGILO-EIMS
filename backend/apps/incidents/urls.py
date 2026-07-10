from rest_framework.routers import DefaultRouter

from .views import IncidentViewSet

router = DefaultRouter()
router.register(r"", IncidentViewSet, basename="incident")

urlpatterns = router.urls

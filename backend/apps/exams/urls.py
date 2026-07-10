from rest_framework.routers import DefaultRouter

from .views import ExamPeriodViewSet, ExamSessionViewSet

router = DefaultRouter()
router.register(r"periods", ExamPeriodViewSet, basename="exam-period")
router.register(r"sessions", ExamSessionViewSet, basename="exam-session")

urlpatterns = router.urls

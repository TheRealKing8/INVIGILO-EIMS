from rest_framework.routers import DefaultRouter

from .views import ExamPeriodViewSet, ExamSessionViewSet, StudentRegistrationViewSet

router = DefaultRouter()
router.register(r"periods", ExamPeriodViewSet, basename="exam-period")
router.register(r"sessions", ExamSessionViewSet, basename="exam-session")
# Phase 15: per-(session, student) registration rows. The nested
# ``sessions/{id}/populate/`` action and the ``{id}/qr.png`` action
# come from the viewset.
router.register(r"registrations", StudentRegistrationViewSet, basename="student-registration")

urlpatterns = router.urls

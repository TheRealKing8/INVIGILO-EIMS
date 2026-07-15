from django.urls import path
from rest_framework.routers import DefaultRouter

from .exports import timetable_ics
from .views import ExamPeriodViewSet, ExamSessionViewSet, StudentRegistrationViewSet

router = DefaultRouter()
router.register(r"periods", ExamPeriodViewSet, basename="exam-period")
router.register(r"sessions", ExamSessionViewSet, basename="exam-session")
# Phase 15: per-(session, student) registration rows. The nested
# ``sessions/{id}/populate/`` action and the ``{id}/qr.png`` action
# come from the viewset.
router.register(r"registrations", StudentRegistrationViewSet, basename="student-registration")

# Phase 18: timetable .ics download. Function view (not a viewset
# action) so the literal ``.ics`` suffix doesn't fight DRF's
# format-suffix router. Same pattern as the attendance CSV
# export in Phase 13 and the per-session .ics in Phase 14.
urlpatterns = router.urls + [
    path("timetable.ics", timetable_ics, name="exam-timetable-ics"),
]

"""URL configuration for ``/api/v1/academic/``."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import (
    CampusViewSet,
    CourseUnitViewSet,
    CourseViewSet,
    DepartmentViewSet,
    FacultyViewSet,
    ProgramViewSet,
    UniversityViewSet,
)

router = DefaultRouter()
router.register(r"universities", UniversityViewSet, basename="university")
router.register(r"campuses", CampusViewSet, basename="campus")
router.register(r"faculties", FacultyViewSet, basename="faculty")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"programs", ProgramViewSet, basename="program")
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"units", CourseUnitViewSet, basename="courseunit")

urlpatterns = router.urls

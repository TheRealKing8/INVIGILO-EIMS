from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from apps.core.permissions import HasPermission

from .models import Campus, Course, CourseUnit, Department, Faculty, Program, University
from .serializers import (
    CampusSerializer,
    CourseSerializer,
    CourseUnitSerializer,
    DepartmentSerializer,
    FacultySerializer,
    ProgramSerializer,
    UniversitySerializer,
)


@extend_schema(tags=["academic"])
class UniversityViewSet(viewsets.ModelViewSet):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [HasPermission.with_codes("academic.university.crud")]
    filterset_fields = ("is_active", "code")
    search_fields = ("code", "name")


@extend_schema(tags=["academic"])
class CampusViewSet(viewsets.ModelViewSet):
    queryset = Campus.objects.select_related("university")
    serializer_class = CampusSerializer
    permission_classes = [HasPermission.with_codes("academic.campus.crud")]
    filterset_fields = ("is_active", "university", "code")
    search_fields = ("code", "name")


@extend_schema(tags=["academic"])
class FacultyViewSet(viewsets.ModelViewSet):
    queryset = Faculty.objects.select_related("campus", "dean")
    serializer_class = FacultySerializer
    permission_classes = [HasPermission.with_codes("academic.faculty.crud")]
    filterset_fields = ("is_active", "code", "campus")
    search_fields = ("code", "name")


@extend_schema(tags=["academic"])
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("faculty", "head")
    serializer_class = DepartmentSerializer
    permission_classes = [HasPermission.with_codes("academic.department.crud")]
    filterset_fields = ("is_active", "faculty", "code")
    search_fields = ("code", "name")


@extend_schema(tags=["academic"])
class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.select_related("department")
    serializer_class = ProgramSerializer
    permission_classes = [HasPermission.with_codes("academic.programme.crud")]
    filterset_fields = ("is_active", "department", "duration_years")
    search_fields = ("code", "name")


@extend_schema(tags=["academic"])
class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("program")
    serializer_class = CourseSerializer
    permission_classes = [HasPermission.with_codes("academic.course.crud")]
    filterset_fields = ("is_active", "program", "credit_hours")
    search_fields = ("code", "title")


@extend_schema(tags=["academic"])
class CourseUnitViewSet(viewsets.ModelViewSet):
    queryset = CourseUnit.objects.select_related("course")
    serializer_class = CourseUnitSerializer
    permission_classes = [HasPermission.with_codes("academic.unit.crud")]
    filterset_fields = ("is_active", "course", "year", "semester")
    search_fields = ("code", "title")

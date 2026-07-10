from rest_framework import serializers

from .models import Campus, Course, CourseUnit, Department, Faculty, Program, University


class UniversitySerializer(serializers.ModelSerializer):
    campus_count = serializers.IntegerField(source="campuses.count", read_only=True)

    class Meta:
        model = University
        fields = (
            "id",
            "code",
            "name",
            "vice_chancellor",
            "campus_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "campus_count",
        )


class CampusSerializer(serializers.ModelSerializer):
    university_code = serializers.CharField(source="university.code", read_only=True)
    faculty_count = serializers.IntegerField(source="faculties.count", read_only=True)

    class Meta:
        model = Campus
        fields = (
            "id",
            "university",
            "university_code",
            "code",
            "name",
            "address",
            "faculty_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "university_code",
            "faculty_count",
        )


class FacultySerializer(serializers.ModelSerializer):
    department_count = serializers.IntegerField(source="departments.count", read_only=True)
    campus_code = serializers.CharField(source="campus.code", read_only=True, default=None)

    class Meta:
        model = Faculty
        fields = (
            "id",
            "code",
            "name",
            "campus",
            "campus_code",
            "dean",
            "department_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "department_count",
            "campus_code",
        )


class DepartmentSerializer(serializers.ModelSerializer):
    faculty_code = serializers.CharField(source="faculty.code", read_only=True)
    faculty_name = serializers.CharField(source="faculty.name", read_only=True)

    class Meta:
        model = Department
        fields = (
            "id",
            "faculty",
            "faculty_code",
            "faculty_name",
            "code",
            "name",
            "head",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "faculty_code", "faculty_name")


class ProgramSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.code", read_only=True)

    class Meta:
        model = Program
        fields = (
            "id",
            "department",
            "department_code",
            "code",
            "name",
            "duration_years",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "department_code")


class CourseSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source="program.code", read_only=True)
    unit_count = serializers.IntegerField(source="units.count", read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "program",
            "program_code",
            "code",
            "title",
            "credit_hours",
            "unit_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "program_code",
            "unit_count",
        )


class CourseUnitSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = CourseUnit
        fields = (
            "id",
            "course",
            "course_code",
            "course_title",
            "code",
            "title",
            "credit_hours",
            "year",
            "semester",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "course_code",
            "course_title",
        )

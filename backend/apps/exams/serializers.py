from rest_framework import serializers

from apps.academic.models import Course
from apps.rooms.models import Room

from .models import ExamPeriod, ExamSession
from .student_registration import StudentRegistration


class ExamPeriodSerializer(serializers.ModelSerializer):
    session_count = serializers.IntegerField(source="sessions.count", read_only=True)

    class Meta:
        model = ExamPeriod
        fields = (
            "id",
            "code",
            "name",
            "starts_on",
            "ends_on",
            "is_active",
            "session_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "session_count")

    def validate(self, attrs):
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts and ends and starts > ends:
            raise serializers.ValidationError(
                {"ends_on": "ends_on must be on or after starts_on"}
            )
        return attrs


class ExamSessionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    period_code = serializers.CharField(source="period.code", read_only=True)
    room_code = serializers.CharField(source="room.code", read_only=True)
    building_code = serializers.CharField(source="room.building.code", read_only=True, default=None)
    course_unit_code = serializers.CharField(
        source="course_unit.code", read_only=True, default=None
    )
    course_unit_year = serializers.IntegerField(
        source="course_unit.year", read_only=True, default=None
    )
    course_unit_semester = serializers.IntegerField(
        source="course_unit.semester", read_only=True, default=None
    )
    faculty_code = serializers.SerializerMethodField()
    faculty_name = serializers.SerializerMethodField()
    department_code = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    program_code = serializers.SerializerMethodField()
    program_name = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    fill_pct = serializers.SerializerMethodField()
    has_allocation = serializers.SerializerMethodField()

    class Meta:
        model = ExamSession
        fields = (
            "id",
            "period",
            "period_code",
            "course",
            "course_code",
            "course_title",
            "course_unit",
            "course_unit_code",
            "course_unit_year",
            "course_unit_semester",
            "faculty_code",
            "faculty_name",
            "department_code",
            "department_name",
            "program_code",
            "program_name",
            "room",
            "room_code",
            "building_code",
            "starts_at",
            "ends_at",
            "duration_minutes",
            "capacity",
            "registered",
            "invigilators_required",
            "status",
            "special_requirements",
            "fill_pct",
            "has_allocation",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "course_code",
            "course_title",
            "period_code",
            "course_unit_code",
            "course_unit_year",
            "course_unit_semester",
            "faculty_code",
            "faculty_name",
            "department_code",
            "department_name",
            "program_code",
            "program_name",
            "room_code",
            "building_code",
            "duration_minutes",
            "fill_pct",
            "has_allocation",
        )

    def get_faculty_code(self, obj: ExamSession) -> str | None:
        return obj.course.program.department.faculty.code if obj.course_id else None

    def get_faculty_name(self, obj: ExamSession) -> str | None:
        return obj.course.program.department.faculty.name if obj.course_id else None

    def get_department_code(self, obj: ExamSession) -> str | None:
        return obj.course.program.department.code if obj.course_id else None

    def get_department_name(self, obj: ExamSession) -> str | None:
        return obj.course.program.department.name if obj.course_id else None

    def get_program_code(self, obj: ExamSession) -> str | None:
        return obj.course.program.code if obj.course_id else None

    def get_program_name(self, obj: ExamSession) -> str | None:
        return obj.course.program.name if obj.course_id else None

    def get_duration_minutes(self, obj: ExamSession) -> int | None:
        if not obj.starts_at or not obj.ends_at:
            return None
        delta = obj.ends_at - obj.starts_at
        return int(delta.total_seconds() // 60)

    def get_fill_pct(self, obj: ExamSession) -> float:
        if not obj.capacity:
            return 0.0
        return round((obj.registered / obj.capacity) * 100, 1)

    def get_has_allocation(self, obj: ExamSession) -> bool:
        return getattr(obj, "_has_allocation", False)

    def validate(self, attrs):
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and starts >= ends:
            raise serializers.ValidationError(
                {"ends_at": "ends_at must be after starts_at"}
            )
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", None))
        registered = attrs.get("registered", getattr(self.instance, "registered", 0))
        if registered and capacity and registered > capacity:
            raise serializers.ValidationError(
                {"registered": "registered cannot exceed capacity"}
            )
        # If a course_unit is provided, it must belong to the same course.
        unit = attrs.get("course_unit", getattr(self.instance, "course_unit", None))
        course = attrs.get("course", getattr(self.instance, "course", None))
        if unit and course and unit.course_id != course.id:
            raise serializers.ValidationError(
                {"course_unit": "course_unit must belong to the selected course"}
            )
        return attrs


class StudentRegistrationSerializer(serializers.ModelSerializer):
    """A per-(session, student) row.

    The ``student_email`` and ``student_name`` denormalised fields
    let the front-end render the registration list without a second
    round-trip to /users/. The ``qr_url`` field gives the printable
    image URL for the door scanner.

    PII gate (Phase 25): a STUDENT viewer — one whose only read
    grant is ``exam.registration.view_own`` and who therefore can
    only see their own row after the viewset's ``get_queryset``
    filter — still gets the email + name on the one row they
    legitimately see (themselves). For any other student row the
    viewset would 404, so the gate below only matters for
    defence-in-depth: if a future refactor accidentally widens
    the queryset, the PII still won't leak. Wide readers
    (EO/SA/HoD/Dean/SecOps) see the fields on every row.
    """

    student_email = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model = StudentRegistration
        fields = (
            "id",
            "session",
            "student",
            "student_email",
            "student_name",
            "student_code",
            "qr_url",
            "created_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "student_email",
            "student_name",
            "qr_url",
        )

    # ------------------------------------------------------------------
    # PII visibility helpers
    # ------------------------------------------------------------------
    def _viewer_can_see_pii(self, obj: StudentRegistration) -> bool:
        """True unless the viewer is a narrow-read student looking at
        somebody else's row.

        The codename check is the same shape the viewset uses in
        ``get_queryset`` — wide readers always pass; everyone else
        must own the row.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        wide_codes = (
            "people.student.crud",
            "exam.session.crud",
            "attendance.view",
        )
        if any(user.has_permission(code) for code in wide_codes):
            return True
        # Narrow-read path: only the row's own student may see PII.
        return obj.student_id == user.id

    def get_student_email(self, obj: StudentRegistration) -> str | None:
        if not self._viewer_can_see_pii(obj):
            return None
        return obj.student.email

    def get_student_name(self, obj: StudentRegistration) -> str | None:
        if not self._viewer_can_see_pii(obj):
            return None
        return obj.student.full_name

    def get_qr_url(self, obj: StudentRegistration) -> str:
        # Relative URL — the frontend concatenates it with the
        # API base. Keeping it relative means a backend behind a
        # reverse proxy / different host still works.
        return f"/api/v1/exams/registrations/{obj.id}/qr.png"

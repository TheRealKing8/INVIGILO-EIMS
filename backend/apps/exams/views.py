from datetime import datetime

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.allocations.models import Allocation
from apps.core.permissions import HasPermission
from apps.invigilators.models import InvigilatorProfile

from .models import ExamPeriod, ExamSession
from .qr import qr_png_response
from .serializers import (
    ExamPeriodSerializer,
    ExamSessionSerializer,
    StudentRegistrationSerializer,
)
from .services import ensure_registrations
from .student_registration import StudentRegistration


# Lifecycle transitions allowed for an ExamSession. Each key is the
# ``status`` value being transitioned TO, and the value is the set of
# statuses from which that transition is permitted. Anything not in this
# map is rejected — we never want a "cancelled" exam silently going back
# to "scheduled", for example.
LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"scheduled", "pending"},
    "scheduled": {"draft", "pending"},
    "ready": {"scheduled"},
    "in_progress": {"ready"},
    "completed": {"in_progress"},
    "cancelled": {"draft", "scheduled", "ready", "pending"},
    "pending": {"scheduled"},
}


# Permission sets used by the session viewset's get_permissions hook.
# ``read`` and ``write`` are split so an invigilator can read +
# create their own session without the ability to delete / mutate
# somebody else's session. Lifecycle actions (cancel, publish, draft,
# reschedule) intentionally stay on the stricter CRUD codename —
# those are admin/officer-only operations.
_SESSION_READ_PERMS = ("exam.session.crud", "exam.session.view")
_SESSION_WRITE_PERMS = ("exam.session.crud", "exam.session.create")
_SESSION_LIFECYCLE_PERMS = ("exam.session.crud",)


@extend_schema(tags=["exams"])
class ExamPeriodViewSet(viewsets.ModelViewSet):
    queryset = ExamPeriod.objects.all()
    serializer_class = ExamPeriodSerializer
    permission_classes = [HasPermission.with_codes("exam.period.crud")]
    filterset_fields = ("is_active", "code")
    search_fields = ("code", "name")

    @extend_schema(
        tags=["exams"],
        summary="Activate a period (deactivates all others).",
        responses={200: ExamPeriodSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):  # type: ignore[no-untyped-def]
        period = self.get_object()
        ExamPeriod.objects.filter(is_active=True).exclude(pk=period.pk).update(is_active=False)
        period.is_active = True
        period.save(update_fields=("is_active", "updated_at"))
        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)


@extend_schema(tags=["exams"])
class ExamSessionViewSet(viewsets.ModelViewSet):
    queryset = ExamSession.objects.select_related(
        "course",
        "course__program",
        "course__program__department",
        "course__program__department__faculty",
        "course_unit",
        "period",
        "room",
        "room__building",
    )
    serializer_class = ExamSessionSerializer
    # Default is the read set; the get_permissions() hook tightens
    # this for write / lifecycle methods.
    permission_classes = [HasPermission.with_codes(*_SESSION_READ_PERMS)]
    filterset_fields = ("status", "period", "room", "course", "invigilators_required", "course_unit")
    ordering_fields = ("starts_at", "registered", "capacity")
    ordering = ("starts_at",)
    search_fields = ("course__code", "course__title", "special_requirements")
    parameters = [
        OpenApiParameter(
            name="period_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter sessions to a single exam period.",
        ),
    ]

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Pick the right permission set per action.

        The viewset is exposed to two populations: admins/officers
        (with the broad ``exam.session.crud``) and invigilators
        (with the narrower ``exam.session.create`` + ``view``). The
        permission sets below list both — ``HasPermission`` matches
        the user as long as they hold **any** of the listed
        codenames.
        """
        lifecycle_actions = {
            "cancel", "draft", "publish", "reschedule",
            "update", "partial_update", "destroy",
        }
        if self.action in lifecycle_actions:
            codes = _SESSION_LIFECYCLE_PERMS
        elif self.action == "create":
            codes = _SESSION_WRITE_PERMS
        else:
            codes = _SESSION_READ_PERMS
        return [HasPermission.with_codes(*codes)()]

    def create(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Create an exam session.

        Behavioural rule: if the caller is an invigilator (i.e. they
        hold ``exam.session.create`` but NOT ``exam.session.crud``)
        and the user has an ``InvigilatorProfile``, a synthetic
        :class:`AllocationRun` + :class:`Allocation` pair is created
        so the invigilator is immediately assigned to the session
        they just added. The synthetic run is the cleanest place to
        put it — every Allocation needs a parent run, and we don't
        want to make ``run`` nullable in the schema just for this
        self-service path.
        """
        from apps.allocations.models import AllocationRun

        response = super().create(request, *args, **kwargs)
        if response.status_code != status.HTTP_201_CREATED:
            return response
        new_session = ExamSession.objects.get(pk=response.data["id"])
        is_invigilator_path = (
            request.user.has_permission("exam.session.create")
            and not request.user.has_permission("exam.session.crud")
        )
        if is_invigilator_path:
            try:
                profile = InvigilatorProfile.objects.get(user=request.user)
            except InvigilatorProfile.DoesNotExist:
                profile = None
            if profile is not None:
                # Synthetic run — not produced by the engine, but
                # the audit trail wants every allocation to have a
                # parent run. Mark runtime_seconds=0 and finished_at
                # = now so the run reads as a completed self-allocate.
                from django.utils import timezone

                run = AllocationRun.objects.create(
                    period=new_session.period,
                    triggered_by=request.user,
                    sessions_total=1,
                    sessions_placed=1,
                    runtime_seconds=0,
                    finished_at=timezone.now(),
                )
                # Allocation has a unique constraint on
                # (session, invigilator) so we key the get_or_create
                # on those two; the run gets attached on the create
                # path. If an existing allocation row already exists
                # (e.g. an admin pre-allocated the invigilator) we
                # leave it alone rather than mutating it.
                Allocation.objects.get_or_create(
                    session=new_session,
                    invigilator=profile,
                    defaults={"run": run, "role": "chief", "status": "confirmed"},
                )
        return response

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def _transition(self, session: ExamSession, target: str) -> tuple[bool, str | None]:
        """Move ``session`` to ``target`` status if the transition is
        permitted. Returns ``(ok, error_message)``."""
        allowed_from = LIFECYCLE_TRANSITIONS.get(target, set())
        if session.status not in allowed_from:
            return (
                False,
                f"cannot transition from '{session.status}' to '{target}'",
            )
        session.status = target
        session.save(update_fields=("status", "updated_at"))
        return True, None

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["exams"],
        summary="Cancel a session.",
        request=None,
        responses={200: ExamSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):  # type: ignore[no-untyped-def]
        session = self.get_object()
        ok, err = self._transition(session, "cancelled")
        if not ok:
            return Response({"detail": err}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["exams"],
        summary="Move a session back to draft (un-publish).",
        request=None,
        responses={200: ExamSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="draft")
    def draft(self, request, pk=None):  # type: ignore[no-untyped-def]
        session = self.get_object()
        ok, err = self._transition(session, "draft")
        if not ok:
            return Response({"detail": err}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["exams"],
        summary="Publish a draft (or pending) session — sets status to 'scheduled'.",
        request=None,
        responses={200: ExamSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):  # type: ignore[no-untyped-def]
        session = self.get_object()
        ok, err = self._transition(session, "scheduled")
        if not ok:
            return Response({"detail": err}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["exams"],
        summary="Reschedule a session to a new starts_at / ends_at.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "starts_at": {"type": "string", "format": "date-time"},
                    "ends_at": {"type": "string", "format": "date-time"},
                    "room": {"type": "string", "format": "uuid"},
                },
                "required": ["starts_at", "ends_at"],
            }
        },
        responses={200: ExamSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):  # type: ignore[no-untyped-def]
        session = self.get_object()
        if session.status in {"in_progress", "completed", "cancelled"}:
            return Response(
                {"detail": f"cannot reschedule a session in '{session.status}' state"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            new_start = datetime.fromisoformat(
                request.data["starts_at"].replace("Z", "+00:00")
            )
            new_end = datetime.fromisoformat(
                request.data["ends_at"].replace("Z", "+00:00")
            )
        except (KeyError, ValueError, TypeError) as exc:
            return Response(
                {"detail": f"invalid starts_at/ends_at: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_start >= new_end:
            return Response(
                {"detail": "starts_at must be earlier than ends_at"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        update_fields = ["starts_at", "ends_at", "updated_at"]
        session.starts_at = new_start
        session.ends_at = new_end
        if "room" in request.data:
            session.room_id = request.data["room"]
            update_fields.append("room")
        session.save(update_fields=update_fields)
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)


# Permission sets used by StudentRegistrationViewSet.
# Read is open to the same roles that can see the attendance roster
# (operations + security). Write is a staff operation (EO).
_REG_READ_PERMS = (
    "people.student.crud",
    "exam.session.crud",
    "attendance.view",
    "exam.session.view_own",
)
_REG_WRITE_PERMS = (
    "people.student.crud",
    "exam.session.crud",
)


@extend_schema(tags=["exams"])
class StudentRegistrationViewSet(viewsets.ModelViewSet):
    """Per-(session, student) registration rows.

    The door scanner endpoint (``/api/v1/attendance/scan/``) takes
    a ``registration_id`` and looks the row up directly. The
    ``qr.png`` action renders a printable PNG of the row's id —
    that's the QR code the student shows on the door card.
    """

    queryset = StudentRegistration.objects.select_related(
        "session", "session__course", "student"
    )
    serializer_class = StudentRegistrationSerializer
    filterset_fields = ("session", "student")
    search_fields = ("student__email", "student__full_name", "student_code")
    ordering_fields = ("session__starts_at", "created_at")
    ordering = ("session__starts_at", "student__email")

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.action in {"list", "retrieve", "qr_png"}:
            return [HasPermission.with_codes(*_REG_READ_PERMS)()]
        return [HasPermission.with_codes(*_REG_WRITE_PERMS)()]

    @extend_schema(
        tags=["exams"],
        summary="Printable QR code (PNG) for the registration row.",
        responses={200: OpenApiResponse(description="PNG image.")},
    )
    @action(detail=True, methods=["get"], url_path="qr.png")
    def qr_png(self, request, pk=None):  # type: ignore[no-untyped-def]
        return qr_png_response(self.get_object())

    @extend_schema(
        tags=["exams"],
        summary="Populate this session's roster from active STUDENT users.",
        responses={
            200: OpenApiResponse(description="`{created: int}` — number of new rows."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"sessions/(?P<session_id>[^/.]+)/populate",
        permission_classes=[HasPermission.with_codes(*_REG_WRITE_PERMS)],
    )
    def populate(self, request, session_id=None):  # type: ignore[no-untyped-def]
        """Walk every active STUDENT user and create a
        :class:`StudentRegistration` row for this session. No-op if
        the session already has any registrations.
        """
        session = get_object_or_404(ExamSession, id=session_id)
        created = ensure_registrations(session)
        return Response({"created": created}, status=status.HTTP_200_OK)

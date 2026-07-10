from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from apps.core.permissions import HasPermission

from .models import Building, Room
from .serializers import BuildingSerializer, RoomSerializer


@extend_schema(tags=["rooms"])
class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = [HasPermission.with_codes("room.crud")]
    filterset_fields = ("is_active", "code")
    search_fields = ("code", "name")


@extend_schema(tags=["rooms"])
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("building")
    serializer_class = RoomSerializer
    permission_classes = [HasPermission.with_codes("room.crud")]
    filterset_fields = ("is_active", "building", "capacity")
    search_fields = ("code", "name", "equipment")

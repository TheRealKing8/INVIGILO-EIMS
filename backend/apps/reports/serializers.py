from rest_framework import serializers

from .models import ReportExport


class ReportExportSerializer(serializers.ModelSerializer):
    generated_by_email = serializers.CharField(
        source="generated_by.email", read_only=True, default=None
    )
    cycle_code = serializers.CharField(source="cycle.code", read_only=True, default=None)
    download_url = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()

    class Meta:
        model = ReportExport
        fields = (
            "id",
            "title",
            "format",
            "audience",
            "cycle",
            "cycle_code",
            "file",
            "download_url",
            "size_bytes",
            "generated_by",
            "generated_by_email",
            "generated_at",
            "parameters",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "generated_by_email",
            "cycle_code",
            "download_url",
            "size_bytes",
            "generated_at",
        )

    def get_download_url(self, obj: ReportExport) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)

    def get_size_bytes(self, obj: ReportExport) -> int:
        if not obj.file:
            return 0
        try:
            return obj.file.size
        except (FileNotFoundError, ValueError):
            return 0

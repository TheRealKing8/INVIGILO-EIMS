"""Serializers for the analytics endpoint.

Most of the response is a flat dict built in
:func:`apps.analytics.services.build_summary`. We expose the
shape to drf-spectacular so the OpenAPI schema describes the
JSON the frontend can rely on.
"""
from __future__ import annotations

from rest_framework import serializers


class WorkloadRowSerializer(serializers.Serializer):
    invigilator_id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField()
    allocated = serializers.IntegerField()
    max_per_cycle = serializers.IntegerField()
    fill_pct = serializers.FloatField()


class AttendanceBucketSerializer(serializers.Serializer):
    week_start = serializers.CharField()
    count = serializers.IntegerField()


class SessionsByDaySerializer(serializers.Serializer):
    date = serializers.CharField()
    count = serializers.IntegerField()
    courses = serializers.ListField(child=serializers.CharField())


class AnalyticsSummarySerializer(serializers.Serializer):
    """Single-endpoint response for the analytics dashboard."""

    period_code = serializers.CharField(allow_null=True)
    period_name = serializers.CharField(allow_null=True)
    coverage = serializers.FloatField(allow_null=True)
    upcoming_sessions_count = serializers.IntegerField()
    checkins_today = serializers.IntegerField()
    late_count_today = serializers.IntegerField()
    open_incidents_count = serializers.IntegerField()
    invigilator_workload = WorkloadRowSerializer(many=True)
    attendance_trend = AttendanceBucketSerializer(many=True)
    sessions_by_day = SessionsByDaySerializer(many=True)
    incidents_by_severity = serializers.DictField(child=serializers.IntegerField())
    generated_at = serializers.DateTimeField()


__all__ = ["AnalyticsSummarySerializer"]

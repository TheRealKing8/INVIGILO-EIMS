"""List periods from a brand-new connection."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.dev")
sys.path.insert(0, r"C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend")
import django
django.setup()

from django.db import connection, transaction
from apps.exams.models import ExamPeriod

# Force a brand-new connection.
connection.close()
connection.ensure_connection()

with connection.cursor() as cur:
    cur.execute("SELECT id, code, name, xmin, age(xmin) FROM exams_examperiod ORDER BY code")
    for r in cur.fetchall():
        print(" ", r)
    print("\n--- raw count of 2026-S2 ---")
    cur.execute("SELECT COUNT(*) FROM exams_examperiod WHERE code='2026-S2'")
    print(" ", cur.fetchone())
    print("\n--- active tx ---")
    cur.execute("SELECT pid, state, query_start, xact_start FROM pg_stat_activity WHERE state='active' AND pid <> pg_backend_pid() ORDER BY query_start DESC LIMIT 10")
    for r in cur.fetchall():
        print(" ", r)

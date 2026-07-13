/**
 * New exam session form — admin + officer entry point.
 *
 * Renders a single-page form with: course (select), course unit
 * (optional, filtered by selected course), period (defaults to the
 * active one), room (optional), start datetime + duration in minutes
 * (the end time is computed), capacity, invigilators required, and
 * a free-text special requirements box. On submit the form POSTs to
 * `/api/v1/exams/sessions/` and pushes the user to the detail page
 * for the new session.
 *
 * Backend permission gating: any user with `exam.session.crud`
 * (admin/officer) or `exam.session.create` (invigilator) can submit.
 * The backend handles the auto-allocate for invigilators.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  createExamSession,
  getActiveExamPeriod,
  getCourses,
  getRooms,
  type Course,
  type ExamPeriod,
  type Room,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

/**
 * Filter CourseUnit options by the selected course. We use the
 * courses-list endpoint and the read-side `course_unit` field would
 * require a separate endpoint, so for now we just present the
 * courses and skip the unit picker — the user can attach a unit
 * later via the engine.
 */

type FormState = {
  courseId: string;
  courseUnitId: string;
  periodId: string;
  roomId: string;
  start: string; // datetime-local
  durationMinutes: string;
  capacity: string;
  invigilatorsRequired: string;
  specialRequirements: string;
  status: "draft" | "scheduled";
};

const EMPTY: FormState = {
  courseId: "",
  courseUnitId: "",
  periodId: "",
  roomId: "",
  start: "",
  durationMinutes: "120",
  capacity: "100",
  invigilatorsRequired: "2",
  specialRequirements: "",
  status: "scheduled",
};

function toIsoUtc(local: string): string {
  // datetime-local has no timezone; the browser interprets it as
  // local time. We send it to the server with the offset the
  // browser tells us, so the server gets a real instant.
  if (!local) return "";
  const d = new Date(local);
  return d.toISOString();
}

export default function NewExamPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: coursesPage } = useFetch(() => getCourses({ page_size: 100 }), []);
  const { data: roomsPage } = useFetch(() => getRooms({ page_size: 100 }), []);
  const { data: activePeriod } = useFetch(() => getActiveExamPeriod(), []);

  const courses: Course[] = coursesPage?.results ?? [];
  const rooms: Room[] = roomsPage?.results ?? [];
  const period: ExamPeriod | null = activePeriod ?? null;

  // Default the period to the active one once we know what it is.
  useEffect(() => {
    if (period && !form.periodId) {
      setForm((f) => ({ ...f, periodId: period.id }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period?.id]);

  const endsAtIso = useMemo(() => {
    if (!form.start || !form.durationMinutes) return "";
    const start = new Date(form.start);
    const end = new Date(start.getTime() + Number(form.durationMinutes) * 60_000);
    return end.toISOString();
  }, [form.start, form.durationMinutes]);

  const canSubmit =
    !!form.courseId &&
    !!form.periodId &&
    !!form.start &&
    !!endsAtIso &&
    Number(form.capacity) > 0 &&
    Number(form.invigilatorsRequired) > 0;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await createExamSession({
        period: form.periodId,
        course: form.courseId,
        course_unit: form.courseUnitId || null,
        room: form.roomId || null,
        starts_at: toIsoUtc(form.start),
        ends_at: endsAtIso,
        capacity: Number(form.capacity),
        registered: 0,
        invigilators_required: Number(form.invigilatorsRequired),
        status: form.status,
        special_requirements: form.specialRequirements || undefined,
      });
      router.push(`/dashboard/exams/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create the exam session. Check the fields and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DashboardShell
      title="New exam session"
      subtitle="Schedule a new exam — pick a course, time, and room"
      actions={
        <Link href="/dashboard/exams">
          <Button variant="ghost" size="md" iconLeft="arrow-right">
            Back to examinations
          </Button>
        </Link>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not create the session">
            {error}
          </StatusBanner>
        </div>
      ) : null}

      <Card>
        <form className="space-y-6" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              label="Course"
              required
              value={form.courseId}
              onChange={(v) => setForm((f) => ({ ...f, courseId: v }))}
              options={courses.map((c) => ({
                value: c.id,
                label: `${c.code} — ${c.title}`,
              }))}
              placeholder="Pick a course…"
            />
            <SelectField
              label="Exam period"
              required
              value={form.periodId}
              onChange={(v) => setForm((f) => ({ ...f, periodId: v }))}
              options={period ? [{ value: period.id, label: `${period.code} — ${period.name}` }] : []}
              placeholder={period ? "Active period" : "No active period — ask admin to activate one"}
              disabled={!period}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Starts at"
              type="datetime-local"
              value={form.start}
              onChange={(e) => setForm((f) => ({ ...f, start: e.target.value }))}
              required
              iconLeft="calendar"
            />
            <Input
              label="Duration (minutes)"
              type="number"
              min={1}
              value={form.durationMinutes}
              onChange={(e) => setForm((f) => ({ ...f, durationMinutes: e.target.value }))}
              hint={`Ends at ${endsAtIso ? new Date(endsAtIso).toLocaleString() : "—"}`}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              label="Room (optional)"
              value={form.roomId}
              onChange={(v) => setForm((f) => ({ ...f, roomId: v }))}
              options={rooms.map((r) => ({
                value: r.id,
                label: `${r.code} — ${r.name} (cap ${r.capacity})`,
              }))}
              placeholder="No room assigned"
            />
            <SelectField
              label="Status"
              value={form.status}
              onChange={(v) => setForm((f) => ({ ...f, status: v as "draft" | "scheduled" }))}
              options={[
                { value: "scheduled", label: "Scheduled (publish immediately)" },
                { value: "draft", label: "Draft (publish later)" },
              ]}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Capacity"
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
              required
            />
            <Input
              label="Invigilators required"
              type="number"
              min={1}
              value={form.invigilatorsRequired}
              onChange={(e) => setForm((f) => ({ ...f, invigilatorsRequired: e.target.value }))}
              required
            />
          </div>

          <div>
            <label
              htmlFor="special_requirements"
              className="mb-1.5 block text-sm font-medium text-ink-700"
            >
              Special requirements
            </label>
            <textarea
              id="special_requirements"
              name="special_requirements"
              rows={3}
              value={form.specialRequirements}
              onChange={(e) => setForm((f) => ({ ...f, specialRequirements: e.target.value }))}
              placeholder="e.g. Large-print papers, extra time (30 min), separate quiet room…"
              className="block w-full rounded-2xl border-0 bg-ink-100/60 px-4 py-3 text-sm text-ink-900 placeholder:text-ink-400 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-ink-100 pt-5">
            <Link href="/dashboard/exams">
              <Button variant="ghost" size="md" type="button">
                Cancel
              </Button>
            </Link>
            <Button
              type="submit"
              size="md"
              variant="primary"
              iconLeft="plus"
              loading={submitting}
              disabled={!canSubmit || submitting}
            >
              {submitting ? "Creating…" : "Create exam session"}
            </Button>
          </div>
        </form>
      </Card>

      <Card className="mt-6">
        <CardHeader
          eyebrow="Tip"
          title="Invigilator self-allocate"
          subtitle="If you create this session as an invigilator, the system will auto-allocate you as the chief invigilator — no need to run the engine."
        />
      </Card>
    </DashboardShell>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder,
  required = false,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
}) {
  return (
    <div>
      <label
        htmlFor={label}
        className="mb-1.5 block text-sm font-medium text-ink-700"
      >
        {label}
        {required ? <span className="ml-0.5 text-rose-600">*</span> : null}
      </label>
      <div className="relative">
        <select
          id={label}
          name={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          disabled={disabled}
          className="block w-full appearance-none rounded-2xl border-0 bg-ink-100/60 px-4 py-3 pr-9 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
        >
          {placeholder ? <option value="">{placeholder}</option> : null}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <Icon
          name="chevron-down"
          className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
        />
      </div>
    </div>
  );
}

/**
 * Per-session student registration list.
 *
 * The EO-facing roster management view for a single exam session. The
 * table is paginated + searchable. The "Populate from department" button
 * calls the backend's idempotent ``ensure_registrations`` service via
 * the ``populate`` action on the registrations viewset. Each row links
 * to the print-friendly QR card view so the EO can bulk-print the
 * student door cards.
 *
 * Visibility is gated on ``people.student.crud`` or
 * ``exam.session.crud``; the backend re-checks the read perm
 * (``attendance.view`` is enough to read the roster) on the underlying
 * endpoints, so the "add" + "populate" buttons only appear when the
 * caller can actually write.
 */
"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  createStudentRegistration,
  deleteStudentRegistration,
  getExamSession,
  getStudentRegistrations,
  populateRegistrations,
  type ExamSession,
  type Paginated,
  type StudentRegistration,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

function initialsOf(name: string | undefined): string {
  if (!name) return "??";
  return name
    .split(/\s+/)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function ExamRegistrationsPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const id = params?.id;
  const { user } = useAuth();

  const [actionError, setActionError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<"populate" | "add" | "delete" | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [addEmail, setAddEmail] = useState("");
  const [addCode, setAddCode] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  // Read perm is enough to render; write buttons are gated separately.
  const canWrite = Boolean(
    user?.permissions?.includes("people.student.crud") ||
      user?.permissions?.includes("exam.session.crud"),
  );

  // The session header is the only thing we need from the parent exam
  // object — no allocations or incidents here. We fetch it so the page
  // can show the course code + start time in the title bar.
  const { data: session } = useFetch<ExamSession | null>(
    async () => (id ? getExamSession(id) : null),
    [id],
  );

  // The table mirrors the backend pagination. We pick up the page
  // from the URL (``?page=2``) so the back button doesn't lose state.
  const page = search?.get("page") ?? "1";
  const search_q = search?.get("q") ?? "";

  const { data, isLoading, error, refresh } = useFetch<{
    regs: Paginated<StudentRegistration> | null;
  }>(
    async () => {
      if (!id) return { regs: null };
      const regs = await getStudentRegistrations({
        session: id,
        page: Number(page) || 1,
        page_size: 50,
        search: search_q || undefined,
      });
      return { regs };
    },
    [id, page, search_q],
  );

  const regs = useMemo(() => data?.regs?.results ?? [], [data?.regs]);
  const total = data?.regs?.count ?? 0;

  async function doPopulate() {
    if (!id) return;
    setActionError(null);
    setActionPending("populate");
    try {
      const out = await populateRegistrations(id);
      await refresh();
      if (out.created === 0) {
        setActionError(
          "This session already has registrations — populate is a no-op. Delete rows manually to re-run.",
        );
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Populate failed");
    } finally {
      setActionPending(null);
    }
  }

  async function doDelete(regId: string) {
    if (!id) return;
    setActionError(null);
    setActionPending("delete");
    setDeletingId(regId);
    try {
      await deleteStudentRegistration(regId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setActionPending(null);
      setDeletingId(null);
    }
  }

  async function doAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!id || !addEmail || !addCode) return;
    setActionError(null);
    setActionPending("add");
    try {
      // Resolve the email to a user id via the admin users endpoint.
      // The student we add must already exist in the system — the
      // backend's FK enforces it.
      const users = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/users/?email=${encodeURIComponent(addEmail)}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("invigilo_access_token") ?? ""}`,
          },
          cache: "no-store",
        },
      );
      if (!users.ok) {
        throw new Error(`Could not look up user (${users.status})`);
      }
      const list = (await users.json()) as Array<{ id: string; email: string }>;
      const target = list.find((u) => u.email.toLowerCase() === addEmail.toLowerCase());
      if (!target) {
        throw new Error(`No user found with email ${addEmail}`);
      }
      await createStudentRegistration({
        session: id,
        student: target.id,
        student_code: addCode,
      });
      setAddEmail("");
      setAddCode("");
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setActionPending(null);
    }
  }

  if (!id) {
    return (
      <DashboardShell title="Registrations" subtitle="Loading…">
        <p className="text-sm text-ink-500">No session id.</p>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      title={
        session
          ? `${session.course_code} — Registrations`
          : "Registrations"
      }
      subtitle={
        session
          ? `${session.course_title ?? ""} · ${new Date(session.starts_at).toLocaleString()}`
          : "Loading…"
      }
      actions={
        <div className="flex items-center gap-2">
          {canWrite ? (
            <>
              <Button
                variant="primary"
                size="md"
                iconLeft="users"
                onClick={() => void doPopulate()}
                disabled={actionPending !== null}
              >
                {actionPending === "populate" ? "Populating…" : "Populate from department"}
              </Button>
              <a
                href={`/dashboard/attendance/${id}/cards/`}
                target="_blank"
                rel="noreferrer"
              >
                <Button variant="ghost" size="md" iconLeft="download">
                  Print QR cards
                </Button>
              </a>
            </>
          ) : null}
          <Button
            variant="ghost"
            size="md"
            iconLeft="arrow-right"
            onClick={() => router.push(`/dashboard/exams/${id}`)}
          >
            <span className="-mt-px inline-block rotate-180">Back to session</span>
          </Button>
        </div>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load registrations">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}
      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone={actionError.startsWith("This session") ? "warning" : "danger"} title="Action notice">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}

      {/* Top counter card */}
      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <Card>
          <p className="eyebrow text-ink-500">Registered students</p>
          <p className="mt-1 text-3xl font-semibold text-ink-900 tnum">{total}</p>
          <p className="mt-1 text-xs text-ink-500">
            {total === 0
              ? "No registrations yet — try Populate."
              : `Across ${total} row${total === 1 ? "" : "s"}.`}
          </p>
        </Card>
        <Card>
          <p className="eyebrow text-ink-500">Capacity</p>
          <p className="mt-1 text-3xl font-semibold text-ink-900 tnum">
            {session?.capacity ?? "—"}
          </p>
          <p className="mt-1 text-xs text-ink-500">
            {session
              ? `${session.registered} expected per the course's plan.`
              : "Loading session…"}
          </p>
        </Card>
      </div>

      {/* Inline add form (EO only) */}
      {canWrite ? (
        <Card className="mb-6">
          <div className="flex items-center justify-between">
            <CardHeader
              eyebrow="Add"
              title="Register a single student"
              subtitle="For ad-hoc additions — most rosters are populated in bulk."
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAdd((v) => !v)}
            >
              {showAdd ? "Cancel" : "Add student"}
            </Button>
          </div>
          {showAdd ? (
            <form onSubmit={doAdd} className="mt-4 grid gap-3 sm:grid-cols-[2fr_2fr_auto]">
              <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Student email
                <input
                  type="email"
                  value={addEmail}
                  onChange={(e) => setAddEmail(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  placeholder="student@invigilo.local"
                />
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Student code
                <input
                  type="text"
                  value={addCode}
                  onChange={(e) => setAddCode(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  placeholder="CS101-2026-0042"
                />
              </label>
              <div className="flex items-end">
                <Button
                  variant="primary"
                  size="md"
                  type="submit"
                  disabled={actionPending === "add"}
                >
                  {actionPending === "add" ? "Adding…" : "Add"}
                </Button>
              </div>
            </form>
          ) : null}
        </Card>
      ) : null}

      {/* Registrations table */}
      <Card padded={false}>
        <div className="border-b border-ink-100 p-5">
          <CardHeader eyebrow="Roster" title="Student registrations" />
        </div>
        {isLoading && regs.length === 0 ? (
          <p className="p-6 text-sm text-ink-500">Loading registrations…</p>
        ) : regs.length === 0 ? (
          <p className="p-6 text-sm text-ink-500">
            No students registered for this session yet.
          </p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {regs.map((r) => (
              <li
                key={r.id}
                className="flex items-center gap-4 px-5 py-3 transition hover:bg-brand-50/30"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
                  {initialsOf(r.student_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink-900">
                    {r.student_name || r.student_email || "—"}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {r.student_email ?? "—"}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <Badge tone="brand">
                    {r.student_code}
                  </Badge>
                </div>
                {canWrite ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void doDelete(r.id)}
                    disabled={actionPending === "delete"}
                  >
                    {deletingId === r.id ? "…" : (
                      <>
                        <Icon name="trash" className="h-3.5 w-3.5" />
                        <span className="sr-only">Remove</span>
                      </>
                    )}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </DashboardShell>
  );
}

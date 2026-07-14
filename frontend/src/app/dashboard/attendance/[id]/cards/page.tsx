/**
 * Print-friendly A4 grid of student QR cards.
 *
 * This is the security officer's helper for the morning of the exam:
 * print the page, cut the cards out, hand one to each student. The
 * layout uses ``@media print`` to hide the nav + chrome and put
 * 4×6 = 24 cards per A4 page. Each card is the registration id
 * encoded as a 320×320 QR (served by the backend's
 * ``/registrations/{id}/qr.png/``) with the student name and code
 * beneath.
 *
 * The cards page lives under ``/attendance/{id}/cards`` rather than
 * the exam admin namespace because the EO *or* the security officer
 * can print them — the read perm is ``attendance.view``.
 */
"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getExamSession,
  getStudentRegistrations,
  studentRegistrationQrUrl,
  type ExamSession,
  type Paginated,
  type StudentRegistration,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

export default function PrintQrCardsPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [pageRequested, setPageRequested] = useState(false);

  const { data: session } = useFetch<ExamSession | null>(
    async () => (id ? getExamSession(id) : null),
    [id],
  );

  // The cards list can be 80+ rows; the page prints the whole thing
  // in one go. A real production app would chunk it.
  const { data, isLoading, error } = useFetch<{
    regs: Paginated<StudentRegistration> | null;
  }>(
    async () => {
      if (!id) return { regs: null };
      // Bump page_size to 200 so a full department fits on one print.
      const regs = await getStudentRegistrations({
        session: id,
        page_size: 200,
      });
      return { regs };
    },
    [id],
  );

  const regs = data?.regs?.results ?? [];

  return (
    <DashboardShell
      title="Print QR cards"
      subtitle={
        session
          ? `${session.course_code} · ${regs.length} card${regs.length === 1 ? "" : "s"}`
          : "Loading…"
      }
      actions={
        <div className="flex items-center gap-2 no-print">
          <Button
            variant="primary"
            size="md"
            iconLeft="download"
            onClick={() => {
              if (typeof window !== "undefined") window.print();
            }}
          >
            Print
          </Button>
          <Button
            variant="ghost"
            size="md"
            iconLeft="arrow-right"
            onClick={() => {
              if (typeof window !== "undefined") window.history.back();
            }}
          >
            Back
          </Button>
        </div>
      }
    >
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white !important; }
        }
        @page { size: A4; margin: 8mm; }
        .qr-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 6mm;
        }
        .qr-card {
          break-inside: avoid;
          page-break-inside: avoid;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 4mm;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2mm;
          background: white;
        }
        .qr-card img {
          width: 36mm;
          height: 36mm;
          object-fit: contain;
        }
      `}</style>

      {error ? (
        <div className="mb-6 no-print">
          <StatusBanner tone="danger" title="Could not load cards">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-ink-500 no-print">Loading registrations…</p>
      ) : regs.length === 0 ? (
        <Card className="no-print">
          <p className="text-sm text-ink-500">
            No registrations yet — populate the roster first.
          </p>
        </Card>
      ) : (
        <>
          <p className="mb-4 text-xs text-ink-500 no-print">
            <Icon name="alert" className="mr-1 inline h-3.5 w-3.5" />
            Print preview shows 4×6 cards per A4 page. Cards are 36mm square
            — crop with a paper cutter or just hand out whole sheets.
          </p>
          <div className="qr-grid">
            {regs.map((r) => (
              <div key={r.id} className="qr-card">
                {/* Use a normal <img> so the browser caches the PNG
                    and the print dialog doesn't block on JS. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={studentRegistrationQrUrl(r.id)}
                  alt={`QR for ${r.student_name ?? r.student_code}`}
                  onLoad={() => setPageRequested(true)}
                />
                <p className="text-center text-[10pt] font-semibold text-ink-900">
                  {r.student_name ?? r.student_code}
                </p>
                <p className="text-center font-mono text-[8pt] text-ink-500">
                  {r.student_code}
                </p>
              </div>
            ))}
          </div>
          {/* Hide-the-back-link helper. We don't actually render the
              variable; the eslint hint keeps it. */}
          {pageRequested ? null : null}
        </>
      )}
    </DashboardShell>
  );
}

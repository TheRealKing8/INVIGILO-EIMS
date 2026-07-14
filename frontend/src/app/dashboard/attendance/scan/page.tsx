/**
 * Door scanner page for security officers.
 *
 * The primary UX is the live camera feed + a small jsQR decode loop
 * that pops a toast on hit. The decode is silent — the user doesn't
 * have to click anything; they just point the camera at the student's
 * QR card and the page calls the backend's
 * ``/api/v1/attendance/scan/`` with the registration id.
 *
 * The signature pad below the camera is optional. The secops draws
 * with the mouse / finger; "Clear" resets; "Use signature" commits the
 * strokes into a PNG and includes the bare base64 in the next scan.
 * A second scan for the same student is a no-op on the server
 * (idempotent) and the first signature wins — re-loading the page
 * after a scan shows the "Present" badge on the roster.
 *
 * Fallback: if the camera is unavailable (desktop, no permission, or
 * the QR is unreadable), the secops can type the student_code by
 * hand. The backend resolves the code → registration via the
 * /registrations/ list endpoint, then runs the same scan action.
 */
"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import jsQR from "jsqr";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getAttendanceRoster,
  getStudentRegistrations,
  scanStudent,
  type Roster,
  type StudentRegistration,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/use-fetch";

// Signature pad constants.
const SIG_WIDTH = 400;
const SIG_HEIGHT = 160;

export default function ScanPage() {
  const router = useRouter();
  const params = useParams<{ id?: string }>();
  const search = useSearchParams();
  // The route is /dashboard/attendance/scan?session={id}, but we
  // also tolerate /dashboard/attendance/[id]/scan/ for symmetry.
  const sessionId = search?.get("session") ?? params?.id ?? null;
  const { user } = useAuth();
  const canScan = Boolean(
    user?.permissions?.includes("attendance.checkin_any"),
  );

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sigCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const drawingRef = useRef<boolean>(false);
  const lastDecodeRef = useRef<{ value: string; at: number } | null>(null);

  const [cameraState, setCameraState] = useState<
    "idle" | "starting" | "live" | "error" | "denied"
  >("idle");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [manualCode, setManualCode] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [lastScan, setLastScan] = useState<{
    student_name: string | null;
    student_code: string;
    at: string;
  } | null>(null);
  const [hasSignature, setHasSignature] = useState(false);

  // Reload the roster after every successful scan so the toast + the
  // back-to-roster link both reflect the new state.
  const { data: roster, refresh: refreshRoster } = useFetch<Roster | null>(
    async () => (sessionId ? getAttendanceRoster(sessionId) : null),
    [sessionId],
  );

  // For the manual-code fallback we look up the registration row from
  // the session + student_code. A real-world UX would do this via a
  // typeahead as the user types; we keep it simple with a 1-look-up
  // on submit.
  const { data: regs } = useFetch<StudentRegistration[]>(
    async () => {
      if (!sessionId) return [];
      const r = await getStudentRegistrations({
        session: sessionId,
        page_size: 200,
      });
      return r.results;
    },
    [sessionId],
  );

  const manualReg = useMemo(() => {
    if (!manualCode) return null;
    return regs?.find((r) => r.student_code === manualCode) ?? null;
  }, [manualCode, regs]);

  // --- Camera lifecycle ------------------------------------------------
  const startCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("error");
      setCameraError("This browser doesn't support camera access.");
      return;
    }
    setCameraState("starting");
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraState("live");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.toLowerCase().includes("permission")) {
        setCameraState("denied");
      } else {
        setCameraState("error");
      }
      setCameraError(msg);
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  // The decode loop — runs while the camera is "live" and submits a
  // scan on the first stable read. To avoid the same QR being
  // re-submitted frame after frame we track the last decoded value
  // and only consider it a new scan if the value has changed OR 1.5
  // seconds have passed.
  useEffect(() => {
    if (cameraState !== "live") return;
    const tick = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const w = video.videoWidth;
      const h = video.videoHeight;
      if (w === 0 || h === 0) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      ctx.drawImage(video, 0, 0, w, h);
      const img = ctx.getImageData(0, 0, w, h);
      const code = jsQR(img.data, img.width, img.height, {
        inversionAttempts: "dontInvert",
      });
      if (code && code.data) {
        const last = lastDecodeRef.current;
        const now = Date.now();
        const isRepeat =
          last && last.value === code.data && now - last.at < 1500;
        lastDecodeRef.current = { value: code.data, at: now };
        if (!isRepeat) {
          void submitScan(code.data);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraState]);

  // Stop the camera when the component unmounts.
  useEffect(() => {
    return () => stopCamera();
  }, [stopCamera]);

  // --- Signature pad ---------------------------------------------------
  const initSignature = useCallback(() => {
    const canvas = sigCanvasRef.current;
    if (!canvas) return;
    canvas.width = SIG_WIDTH;
    canvas.height = SIG_HEIGHT;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, []);

  useEffect(() => {
    initSignature();
  }, [initSignature]);

  function getCanvasPos(
    e: React.MouseEvent | React.TouchEvent,
  ): { x: number; y: number } | null {
    const canvas = sigCanvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    if ("touches" in e) {
      const t = e.touches[0] ?? e.changedTouches[0];
      if (!t) return null;
      return { x: (t.clientX - rect.left) * scaleX, y: (t.clientY - rect.top) * scaleY };
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function onSigStart(e: React.MouseEvent | React.TouchEvent) {
    e.preventDefault();
    const ctx = sigCanvasRef.current?.getContext("2d");
    const pos = getCanvasPos(e);
    if (!ctx || !pos) return;
    drawingRef.current = true;
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  }

  function onSigMove(e: React.MouseEvent | React.TouchEvent) {
    if (!drawingRef.current) return;
    e.preventDefault();
    const ctx = sigCanvasRef.current?.getContext("2d");
    const pos = getCanvasPos(e);
    if (!ctx || !pos) return;
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    setHasSignature(true);
  }

  function onSigEnd() {
    drawingRef.current = false;
  }

  function clearSignature() {
    initSignature();
    setHasSignature(false);
  }

  function captureSignature(): string {
    const canvas = sigCanvasRef.current;
    if (!canvas) return "";
    // The data URL is "data:image/png;base64,...."; the backend
    // strips the prefix and validates the rest.
    return canvas.toDataURL("image/png");
  }

  // --- Submission ------------------------------------------------------
  async function submitScan(registrationId: string) {
    if (!sessionId) return;
    setActionError(null);
    setActionPending(true);
    try {
      const sig = hasSignature ? captureSignature() : "";
      const out = await scanStudent(sessionId, registrationId, {
        signature_png: sig,
      });
      // We don't have the student name from the scan response, but
      // the back-end returns user_email which we can use to look up
      // the registration row.
      const reg = regs?.find((r) => r.id === registrationId);
      setLastScan({
        student_name: reg?.student_name ?? null,
        student_code: reg?.student_code ?? "—",
        at: out.at,
      });
      // Reset the signature pad after a successful scan so the
      // next student signs a fresh one.
      if (hasSignature) clearSignature();
      await refreshRoster();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setActionPending(false);
    }
  }

  async function submitManual() {
    if (!manualReg) {
      setActionError("No registered student found with that code.");
      return;
    }
    await submitScan(manualReg.id);
    setManualCode("");
  }

  if (!sessionId) {
    return (
      <DashboardShell title="Scan" subtitle="Loading…">
        <p className="text-sm text-ink-500">No session selected.</p>
      </DashboardShell>
    );
  }

  if (!canScan) {
    return (
      <DashboardShell
        title="Scan"
        subtitle="Door scanner"
        actions={
          <Button
            variant="ghost"
            size="md"
            iconLeft="arrow-right"
            onClick={() => router.push("/dashboard/attendance")}
          >
            <span className="-mt-px inline-block rotate-180">Back</span>
          </Button>
        }
      >
        <Card>
          <p className="text-sm text-ink-500">
            You need the <code>attendance.checkin_any</code> permission to
            use the door scanner. Contact your examination officer.
          </p>
        </Card>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      title="Door scanner"
      subtitle={
        roster
          ? `${roster.session.course_code} · ${fmtTime(roster.session.starts_at)} – ${fmtTime(roster.session.ends_at)}`
          : "Loading…"
      }
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="md"
            iconLeft="users"
            onClick={() => router.push(`/dashboard/attendance/${sessionId}`)}
          >
            Open roster
          </Button>
          <Button
            variant="ghost"
            size="md"
            iconLeft="arrow-right"
            onClick={() => router.push("/dashboard/attendance")}
          >
            <span className="-mt-px inline-block rotate-180">Back</span>
          </Button>
        </div>
      }
    >
      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Scan failed">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}
      {lastScan ? (
        <div className="mb-6">
          <StatusBanner tone="success" title="Check-in recorded">
            <strong>{lastScan.student_name ?? lastScan.student_code}</strong>{" "}
            · {lastScan.student_code} · {fmtDateTime(lastScan.at)}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Camera + manual fallback */}
        <div className="space-y-4">
          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Camera"
                title="Point at a student QR"
                subtitle="The page auto-submits when a new code is detected."
              />
            </div>
            <div className="relative aspect-video w-full overflow-hidden bg-ink-900">
              <video
                ref={videoRef}
                playsInline
                muted
                className="h-full w-full object-cover"
              />
              <canvas ref={canvasRef} className="hidden" />
              {/* Targeting overlay — a static reticle, drawn on top. */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-1/2 w-2/3 rounded-3xl border-2 border-white/70 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
              </div>
              {cameraState === "idle" || cameraState === "error" || cameraState === "denied" ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink-900/80 text-center text-sm text-white">
                  <Icon name="camera" className="h-8 w-8" />
                  {cameraState === "denied" ? (
                    <p>Camera permission denied. Use the manual code field on the right.</p>
                  ) : cameraState === "error" ? (
                    <p>{cameraError ?? "Camera failed to start."}</p>
                  ) : (
                    <p>Start the camera to begin scanning.</p>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => void startCamera()}
                    iconLeft="camera"
                  >
                    Start camera
                  </Button>
                </div>
              ) : null}
              {cameraState === "starting" ? (
                <div className="absolute inset-0 flex items-center justify-center bg-ink-900/80 text-sm text-white">
                  <p>Starting camera…</p>
                </div>
              ) : null}
              {cameraState === "live" ? (
                <div className="absolute right-3 top-3 flex items-center gap-2 rounded-full bg-emerald-600/90 px-3 py-1 text-[10px] font-semibold text-white">
                  <span className="h-1.5 w-1.5 rounded-full bg-white" />
                  Live
                </div>
              ) : null}
            </div>
            <div className="flex items-center justify-between gap-2 p-4 text-xs text-ink-500">
              <span>
                {cameraState === "live"
                  ? "Hold the student card inside the box. Auto-submits on detect."
                  : "Camera off — use the manual fallback or click Start."}
              </span>
              {cameraState === "live" ? (
                <Button variant="ghost" size="sm" onClick={stopCamera}>
                  Stop
                </Button>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardHeader
              eyebrow="Fallback"
              title="Type the student code"
              subtitle="If the camera can't read the card, the secops can type the code printed beneath the QR."
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void submitManual();
              }}
              className="mt-4 flex items-end gap-2"
            >
              <label className="block flex-1 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Student code
                <input
                  type="text"
                  value={manualCode}
                  onChange={(e) => setManualCode(e.target.value.toUpperCase())}
                  className="mt-1 block w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  placeholder="CS101-2026-0042"
                />
              </label>
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={!manualReg || actionPending}
              >
                {actionPending ? "Checking in…" : "Check in"}
              </Button>
            </form>
            {manualCode && !manualReg ? (
              <p className="mt-2 text-xs text-amber-700">
                No student with that code is registered for this session.
              </p>
            ) : null}
            {manualReg ? (
              <p className="mt-2 text-xs text-ink-500">
                Match: {manualReg.student_name ?? manualReg.student_email}
              </p>
            ) : null}
          </Card>
        </div>

        {/* Signature pad + roster snapshot */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              eyebrow="E-signature"
              title="Capture the student's signature"
              subtitle="Optional. Drawn once and submitted with the next scan."
            />
            <div className="mt-4 overflow-hidden rounded-xl ring-1 ring-ink-200">
              <canvas
                ref={sigCanvasRef}
                onMouseDown={onSigStart}
                onMouseMove={onSigMove}
                onMouseUp={onSigEnd}
                onMouseLeave={onSigEnd}
                onTouchStart={onSigStart}
                onTouchMove={onSigMove}
                onTouchEnd={onSigEnd}
                className="block w-full touch-none bg-white"
                style={{ aspectRatio: `${SIG_WIDTH} / ${SIG_HEIGHT}` }}
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={clearSignature}
                iconLeft="x"
              >
                Clear
              </Button>
              {hasSignature ? (
                <Badge tone="success" withDot>
                  Signature ready
                </Badge>
              ) : (
                <Badge tone="neutral">Empty</Badge>
              )}
            </div>
          </Card>

          {roster ? (
            <Card padded={false}>
              <div className="border-b border-ink-100 p-5">
                <CardHeader
                  eyebrow="Now"
                  title="Live roster"
                  subtitle={`${roster.totals.student.present} of ${roster.totals.student.expected} students present`}
                />
              </div>
              <ul className="max-h-80 divide-y divide-ink-100 overflow-y-auto">
                {roster.students.length === 0 ? (
                  <li className="p-6 text-sm text-ink-500">
                    No students on the roster.
                  </li>
                ) : (
                  roster.students.map((r) => (
                    <li
                      key={r.user_id}
                      className="flex items-center gap-3 px-5 py-2 text-sm"
                    >
                      <span className="flex-1 truncate font-medium text-ink-900">
                        {r.full_name || r.email}
                      </span>
                      {r.present ? (
                        <Badge tone={r.late ? "warning" : "success"} withDot>
                          {r.late ? "Late" : "Present"}
                        </Badge>
                      ) : (
                        <Badge tone="neutral">Absent</Badge>
                      )}
                    </li>
                  ))
                )}
              </ul>
            </Card>
          ) : null}
        </div>
      </div>
    </DashboardShell>
  );
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type AuthUser = {
  id: string;
  email: string;
  full_name?: string;
  primary_role?: string;
  role?: string | null;
  /**
   * Permission codenames granted to the user, sourced from the
   * ``permissions`` JWT claim at login time. The list is the union
   * across all of the user's active roles. The server is still the
   * source of truth — this is for client-side gating only.
   */
  permissions?: string[];
  is_email_verified?: boolean;
  is_staff?: boolean;
};

export type AuthTokens = {
  access: string;
  /**
   * The raw refresh token. The browser will normally NOT see this
   * — the server sets it as an httpOnly cookie on login/register.
   * The field is included in the response body for non-browser
   * clients (CLI, mobile, tests) and when the server is configured
   * with ``JWT_INCLUDE_REFRESH_IN_BODY=true``.
   */
  refresh?: string;
  access_lifetime_seconds?: number;
  refresh_lifetime_seconds?: number;
  user: AuthUser;
};

/**
 * Discriminated union for the login response. The first step may
 * return a token pair (most roles) OR a request to complete the
 * OTP second step (currently SYSTEM_ADMINISTRATOR). The client
 * branches on ``requires_otp`` to decide which view to show.
 */
export type LoginResult =
  | { requires_otp: true; otp_token: string }
  | AuthTokens;

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------
export type Paginated<T> = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type ExamSession = {
  id: string;
  period: string;
  period_code?: string;
  course: string;
  course_code?: string;
  course_title?: string;
  course_unit?: string | null;
  course_unit_code?: string | null;
  course_unit_year?: number | null;
  course_unit_semester?: number | null;
  faculty_code?: string | null;
  faculty_name?: string | null;
  department_code?: string | null;
  department_name?: string | null;
  program_code?: string | null;
  program_name?: string | null;
  room: string | null;
  room_code?: string | null;
  building_code?: string | null;
  starts_at: string;
  ends_at: string;
  duration_minutes?: number | null;
  capacity: number;
  registered: number;
  invigilators_required: number;
  status: "draft" | "scheduled" | "ready" | "in_progress" | "pending" | "completed" | "cancelled";
  special_requirements?: string;
  fill_pct?: number;
  has_allocation?: boolean;
  created_at: string;
  updated_at: string;
};

export type ExamPeriod = {
  id: string;
  code: string;
  name: string;
  starts_on: string;
  ends_on: string;
  is_active: boolean;
  session_count?: number;
  created_at: string;
  updated_at: string;
};

export type InvigilatorProfile = {
  id: string;
  user: string;
  primary_department: string | null;
  primary_department_code?: string | null;
  primary_department_name?: string | null;
  max_sessions_per_cycle: number;
  rating: string;
  user_email?: string;
  user_full_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Allocation = {
  id: string;
  run: string;
  session: string;
  exam_code?: string;
  exam_title?: string;
  session_starts_at?: string;
  session_ends_at?: string;
  invigilator: string;
  invigilator_name?: string;
  invigilator_department?: string | null;
  room: string | null;
  room_code?: string | null;
  building_code?: string | null;
  role: string;
  status: "draft" | "confirmed" | "rejected";
  created_at: string;
  updated_at: string;
};

export type AllocationRun = {
  id: string;
  period: string;
  period_code?: string;
  triggered_by: string | null;
  triggered_by_email?: string | null;
  sessions_total: number;
  sessions_placed: number;
  avg_workload: string;
  max_workload: number;
  capacity_utilisation: string;
  runtime_seconds: number;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Conflict = {
  id: string;
  run: string;
  session: string | null;
  session_code?: string | null;
  invigilator: string | null;
  invigilator_name?: string | null;
  type:
    | "double_booking"
    | "dept_mix"
    | "no_eligible_invigilators"
    | "no_room_capacity"
    | "workload_cap"
    | "unavailability";
  severity: "warning" | "error";
  detail: string;
  created_at: string;
};

export type Incident = {
  id: string;
  title: string;
  body: string;
  session: string | null;
  session_code?: string | null;
  session_starts_at?: string | null;
  room_code?: string | null;
  reporter: string | null;
  reporter_email?: string | null;
  reporter_name?: string | null;
  severity: "low" | "medium" | "high" | "critical";
  status: "open" | "investigating" | "escalated" | "resolved";
  reported_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolved_by_email?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type Room = {
  id: string;
  building: string;
  building_code?: string | null;
  building_name?: string | null;
  code: string;
  name: string;
  capacity: number;
  equipment?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Course = {
  id: string;
  program: string;
  program_code?: string | null;
  program_name?: string | null;
  code: string;
  title: string;
  credit_hours: number;
  created_at?: string;
  updated_at?: string;
};

export type RoleSummary = {
  id: string;
  code: string;
  name: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  avatar_url: string;
  time_zone: string;
  is_active: boolean;
  is_email_verified: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  failed_login_count: number;
  locked_until: string | null;
  created_at: string;
  updated_at: string;
  primary_role: string | null;
  roles: RoleSummary[];
};

export type AuditLog = {
  id: string;
  actor: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  path: string;
  method: string;
  request_id: string | null;
  created_at: string;
};

export type ReportExport = {
  id: string;
  title: string;
  format: "pdf" | "excel" | "csv";
  audience: "internal" | "registrar" | "senate" | "public";
  cycle: string | null;
  cycle_code?: string | null;
  file: string | null;
  download_url: string | null;
  size_bytes: number;
  generated_by: string | null;
  generated_by_email?: string | null;
  generated_at: string;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DashboardSummary = {
  active_period: ExamPeriod | null;
  total_sessions: number;
  total_invigilators: number;
  total_incidents_open: number;
  recent_runs: AllocationRun[];
  upcoming_sessions: ExamSession[];
  recent_incidents: Incident[];
};

// ---------------------------------------------------------------------------
// Analytics (Phase 16)
// ---------------------------------------------------------------------------
// Shape mirrors the AnalyticsSummaryView response in
// `backend/apps/analytics/views.py` — single aggregator endpoint that
// returns the full control-room view in one round-trip. See
// `apps/analytics/services.py` for the per-slice query details and
// the role-based scoping (INVIGILATOR gets a workload list narrowed
// to their own allocations; everything else is org-wide).
export type AnalyticsWorkloadRow = {
  name: string;
  email: string;
  allocated: number;
  max_per_cycle: number;
  fill_pct: number;
};

export type AnalyticsAttendanceBucket = {
  week_start: string; // ISO date (Monday of the bucket)
  count: number;
};

export type AnalyticsSessionsByDay = {
  date: string; // ISO date
  count: number;
  courses: string[];
};

export type AnalyticsIncidentsBySeverity = {
  low: number;
  medium: number;
  high: number;
  critical: number;
};

export type AnalyticsSummary = {
  period_code: string | null;
  coverage: number | null; // 0–100 (AllocationRun.capacity_utilisation × 100)
  upcoming_sessions_count: number;
  checkins_today: number;
  late_count_today: number;
  open_incidents_count: number;
  invigilator_workload: AnalyticsWorkloadRow[];
  attendance_trend: AnalyticsAttendanceBucket[]; // 12 weekly buckets
  sessions_by_day: AnalyticsSessionsByDay[]; // next 7 days
  incidents_by_severity: AnalyticsIncidentsBySeverity;
  generated_at: string; // ISO datetime
};

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------
const STORAGE_KEYS = {
  access: "invigilo_access_token",
  user: "invigilo_user",
} as const;

export function saveAuthTokens(accessToken: string, user?: AuthUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.access, accessToken);
  if (user) {
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
  } else {
    localStorage.removeItem(STORAGE_KEYS.user);
  }
}

export function getStoredAccessToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.access);
}

/**
 * No-op retained for backward compatibility. The refresh token is now
 * stored by the browser as an httpOnly cookie (``invigilo_rt``) and
 * travels automatically on every request to the API. The frontend
 * never sees or persists the raw value.
 */
export function getStoredRefreshToken(): string | null {
  return null;
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  const rawUser = localStorage.getItem(STORAGE_KEYS.user);
  if (!rawUser) return null;
  try {
    return JSON.parse(rawUser) as AuthUser;
  } catch {
    return null;
  }
}

export function clearAuthTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.access);
  localStorage.removeItem(STORAGE_KEYS.user);
}

// ---------------------------------------------------------------------------
// Core request — adds Authorization header from storage.
// On 401, attempts a single refresh; on second 401, clears tokens and
// throws. The 401 callback (passed in by the client) handles redirecting
// to /login so server-rendered routes don't end up in a redirect loop.
//
// The browser attaches the httpOnly ``invigilo_rt`` cookie on
// /api/v1/auth/refresh/ and /api/v1/auth/logout/ so the server can
// rotate or revoke it. All cross-origin requests to the API carry
// ``credentials: 'include'`` for that reason.
// ---------------------------------------------------------------------------
let onUnauthenticated: (() => void) | null = null;
export function setOnUnauthenticated(cb: () => void) {
  onUnauthenticated = cb;
}

function needsCredentials(path: string): boolean {
  return path.startsWith("/api/v1/auth/");
}

async function rawRequest<T>(path: string, init: RequestInit, accessToken?: string): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: needsCredentials(path) ? "include" : init.credentials ?? "same-origin",
    cache: "no-store",
  });
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message =
      typeof data === "string" ? data : data?.detail || data?.message || `Request failed: ${response.status}`;
    const err = new Error(message) as Error & { status?: number };
    err.status = response.status;
    throw err;
  }
  return data as T;
}

export async function requestWithAuth<T>(path: string, init: RequestInit = {}): Promise<T> {
  const access = getStoredAccessToken();
  try {
    return await rawRequest<T>(path, init, access ?? undefined);
  } catch (err) {
    const status = (err as { status?: number }).status;
    if (status !== 401 && status !== 403) {
      throw err;
    }
    if (!access) {
      throw err;
    }
    // A 401 is "access token expired" — refresh + retry is always
    // correct. A 403 is normally a real authorization decision and we
    // would NOT retry — but for the dashboard we treat it as a stale
    // ``permissions`` claim when the access token is still alive
    // (the refresh cookie is valid, the server's role/permission
    // state just moved on since the JWT was minted). One refresh +
    // retry: if the new token now carries the required codename, the
    // call succeeds. If it still 403s, that's a real authorization
    // decision and we surface the original error.
    //
    // We don't extend this recovery to the auth *action* endpoints
    // (login, refresh, verify-otp, logout, register, password
    // reset) — a 403 there is meaningful (e.g. trying to logout
    // without a refresh cookie). Critically, this list is a
    // hand-maintained set of action-path *suffixes*, not a prefix
    // like ``/api/v1/auth/`` — the prefix would also match
    // ``/api/v1/auth/me/`` and silently skip the refresh-retry on
    // the dashboard's primary 403 case. See
    // ``invigilo-phase-11-otp-dev-403-refresh.md``.
    const isAuthAction = [
      "/login/",
      "/refresh/",
      "/verify-otp/",
      "/logout/",
      "/register/",
      "/password/reset/",
      "/password/reset/confirm/",
    ].some((s) => path.endsWith(s));
    if (status === 403 && isAuthAction) {
      throw err;
    }
    // Try a refresh. The browser attaches the httpOnly cookie; the
    // server rotates the cookie and returns a fresh access token.
    try {
      const tokens = await rawRequest<{ access: string }>(
        "/api/v1/auth/refresh/",
        { method: "POST", body: JSON.stringify({}) },
      );
      // ``tokens.refresh`` may be present in non-browser responses, but
      // the web client never reads it — the new refresh is in the
      // rotated cookie, which travels automatically from now on.
      saveAuthTokens(tokens.access);
      // Retry once with the new access token.
      return await rawRequest<T>(path, init, tokens.access);
    } catch (refreshErr) {
      // The refresh itself failed (refresh cookie gone or revoked).
      // Clear local tokens and let the auth callback redirect.
      clearAuthTokens();
      onUnauthenticated?.();
      throw refreshErr;
    }
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return rawRequest<T>(path, init ?? {});
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

// ---------------------------------------------------------------------------
// Health + auth
// ---------------------------------------------------------------------------
export async function getHealth() {
  return request<{ status: string; db: string; redis: string; migrations: string }>(
    "/api/health/",
  );
}

export async function loginWithEmailPassword(
  email: string,
  password: string,
): Promise<LoginResult> {
  return request<LoginResult>("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

/**
 * Complete the second step of an admin login.
 *
 * Returns the same shape as a normal login (token pair + user) on
 * success. Throws on any failure (wrong code, expired token,
 * exhausted attempts) so the caller can render a single error.
 */
export async function verifyLoginOtp(
  otpToken: string,
  code: string,
): Promise<AuthTokens> {
  return request<AuthTokens>("/api/v1/auth/verify-otp/", {
    method: "POST",
    body: JSON.stringify({ otp_token: otpToken, code }),
  });
}

export async function registerWithEmailPassword(
  fullName: string,
  email: string,
  password: string,
): Promise<AuthTokens> {
  return request<AuthTokens>("/api/v1/auth/register/", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
}

export async function getProfile(accessToken: string): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/me/", {
    headers: bearer(accessToken),
  });
}

/**
 * Same as :func:`getProfile` but uses the auth-aware ``requestWithAuth``
 * so the access token comes from localStorage automatically. We use
 * this on the dashboard home to re-read the live ``primary_role`` from
 * the server — the value baked into the JWT at login time can drift
 * out of sync after a role change (e.g. an admin demoted themselves
 * via the new ``/dashboard/users/{id}/set-roles/`` endpoint while
 * still signed in).
 *
 * The endpoint requires only ``IsAuthenticated``; a 401 here would
 * mean the refresh cookie is gone and the SPA should sign out.
 */
export async function getMe(): Promise<AuthUser> {
  return requestWithAuth<AuthUser>("/api/v1/auth/me/");
}

export async function requestPasswordReset(email: string): Promise<void> {
  await request<void>("/api/v1/auth/password/reset/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<void> {
  await request<void>("/api/v1/auth/password/reset/confirm/", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export async function logoutRequest(): Promise<void> {
  // The browser attaches the httpOnly refresh cookie; the server
  // revokes it and clears the cookie on the way out. No body needed.
  await request<void>("/api/v1/auth/logout/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

// ---------------------------------------------------------------------------
// Domain wrappers
// ---------------------------------------------------------------------------
function qs(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (!entries.length) return "";
  return `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()}`;
}

// Exams
export const getExamSessions = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<ExamSession>>(`/api/v1/exams/sessions/${qs(params)}`);
export const getExamSession = (id: string) =>
  requestWithAuth<ExamSession>(`/api/v1/exams/sessions/${id}/`);
export const getExamPeriods = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<ExamPeriod>>(`/api/v1/exams/periods/${qs(params)}`);
export const getActiveExamPeriod = () =>
  requestWithAuth<Paginated<ExamPeriod>>(
    `/api/v1/exams/periods/${qs({ is_active: "true", page_size: 1 })}`,
  ).then((p) => p.results[0] ?? null);

// Courses
export const getCourses = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Course>>(`/api/v1/academic/courses/${qs(params)}`);

/**
 * Create an exam session. Returns the full session object on 201.
 *
 * Payload shape mirrors ExamSessionSerializer's writable fields; see
 * `backend/apps/exams/serializers.py` for validation rules
 * (starts_at < ends_at, course_unit must belong to course, etc.).
 */
export async function createExamSession(payload: {
  period: string;
  course: string;
  course_unit?: string | null;
  room?: string | null;
  starts_at: string;
  ends_at: string;
  capacity: number;
  registered?: number;
  invigilators_required?: number;
  status?: ExamSession["status"];
  special_requirements?: string;
}): Promise<ExamSession> {
  return requestWithAuth<ExamSession>("/api/v1/exams/sessions/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Lifecycle actions for an ExamSession. The backend enforces the
 * allowed transitions (e.g. you cannot publish a "cancelled" session);
 * a 409 from the server surfaces a friendly error to the caller.
 */
export async function cancelExamSession(id: string): Promise<ExamSession> {
  return requestWithAuth<ExamSession>(
    `/api/v1/exams/sessions/${id}/cancel/`,
    { method: "POST" },
  );
}

export async function draftExamSession(id: string): Promise<ExamSession> {
  return requestWithAuth<ExamSession>(
    `/api/v1/exams/sessions/${id}/draft/`,
    { method: "POST" },
  );
}

export async function publishExamSession(id: string): Promise<ExamSession> {
  return requestWithAuth<ExamSession>(
    `/api/v1/exams/sessions/${id}/publish/`,
    { method: "POST" },
  );
}

export async function rescheduleExamSession(
  id: string,
  body: { starts_at: string; ends_at: string; room?: string },
): Promise<ExamSession> {
  return requestWithAuth<ExamSession>(
    `/api/v1/exams/sessions/${id}/reschedule/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

// Invigilators
export const getInvigilators = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<InvigilatorProfile>>(`/api/v1/invigilators/profiles/${qs(params)}`);

/**
 * Per-date availability override for an invigilator. The default is
 * "available" (no row); a row expresses "busy" / "off_duty" / "leave"
 * for a particular date. The allocation engine filters candidates
 * by combining ``profile.is_active``, ``profile.user.is_active`` and
 * any matching ``Availability`` row for the session's date — see
 * ``backend/apps/allocations/services/engine.py:115-130``.
 */
export type Availability = {
  id: string;
  invigilator: string;
  invigilator_email?: string;
  invigilator_name?: string;
  date: string; // YYYY-MM-DD
  status: "available" | "busy" | "off_duty" | "leave";
  note: string;
};

export const getAvailability = (
  params: Record<string, string | number | undefined>,
) =>
  requestWithAuth<Paginated<Availability>>(
    `/api/v1/invigilators/availability/${qs(params)}`,
  );

/**
 * Create or update an availability row. The backend enforces
 * ``unique_together = (("invigilator", "date"))`` — a second POST
 * for the same (invigilator, date) returns 400. The UI treats that
 * as a refresh signal and re-fetches the current state.
 */
export const setAvailability = (payload: {
  invigilator: string;
  date: string;
  status: Availability["status"];
  note?: string;
}): Promise<Availability> =>
  requestWithAuth<Availability>("/api/v1/invigilators/availability/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Allocations
export const getAllocations = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Allocation>>(`/api/v1/allocations/allocations/${qs(params)}`);
export const getAllocationRuns = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<AllocationRun>>(`/api/v1/allocations/runs/${qs(params)}`);
export const getAllocationRun = (id: string) =>
  requestWithAuth<AllocationRun>(`/api/v1/allocations/runs/${id}/`);
export const getAllocationsForRun = (runId: string) =>
  requestWithAuth<Paginated<Allocation>>(
    `/api/v1/allocations/allocations/${qs({ run: runId, page_size: 100 })}`,
  );
export const getAllocationForSession = (sessionId: string) =>
  requestWithAuth<Paginated<Allocation>>(
    `/api/v1/allocations/allocations/${qs({ session: sessionId, page_size: 50 })}`,
  );
export const getConflicts = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Conflict>>(`/api/v1/allocations/conflicts/${qs(params)}`);

export async function runAllocationEngine(periodId: string): Promise<AllocationRun> {
  return requestWithAuth<AllocationRun>("/api/v1/allocations/runs/", {
    method: "POST",
    body: JSON.stringify({ period_id: periodId }),
  });
}

// Incidents
export const getIncidents = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Incident>>(`/api/v1/incidents/${qs(params)}`);
export const getIncidentsForSession = (sessionId: string) =>
  requestWithAuth<Paginated<Incident>>(
    `/api/v1/incidents/${qs({ session: sessionId, page_size: 50 })}`,
  );

export async function createIncident(payload: {
  title: string;
  body?: string;
  session?: string;
  severity?: Incident["severity"];
}): Promise<Incident> {
  return requestWithAuth<Incident>("/api/v1/incidents/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateIncidentStatus(
  id: string,
  status: Incident["status"],
): Promise<Incident> {
  return requestWithAuth<Incident>(`/api/v1/incidents/${id}/set-status/`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export const getIncident = (id: string) =>
  requestWithAuth<Incident>(`/api/v1/incidents/${id}/`);

// ---------------------------------------------------------------------------
// Attendance
// ---------------------------------------------------------------------------
export type CheckIn = {
  id: string;
  session: string;
  session_code?: string | null;
  session_starts_at?: string | null;
  user: string;
  user_email?: string;
  user_name?: string;
  kind: "invigilator" | "student";
  method: "self" | "bulk";
  at: string;
  late: boolean;
  location: string;
  recorded_by: string;
  recorded_by_email?: string | null;
  created_at?: string;
};

export type RosterEntry = {
  user_id: string;
  email: string;
  full_name: string;
  kind: "invigilator" | "student";
  present: boolean;
  late: boolean;
  at: string | null;
  method: "self" | "bulk" | null;
  location: string;
  recorded_by_email: string | null;
};

export type RosterTotals = {
  present: number;
  expected: number;
  late: number;
};

export type Roster = {
  session: {
    id: string;
    course_code: string;
    course_title: string;
    room_code: string | null;
    starts_at: string;
    ends_at: string;
    status: ExamSession["status"];
  };
  invigilators: RosterEntry[];
  students: RosterEntry[];
  totals: {
    invigilator: RosterTotals;
    student: RosterTotals;
  };
};

export const getAttendanceRoster = (sessionId: string) =>
  requestWithAuth<Roster>(`/api/v1/attendance/sessions/${sessionId}/roster/`);

export async function selfCheckIn(
  sessionId: string,
  kind: CheckIn["kind"],
  location?: string,
): Promise<CheckIn> {
  return requestWithAuth<CheckIn>("/api/v1/attendance/", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      kind,
      location: location ?? "",
    }),
  });
}

export async function bulkCheckIn(
  sessionId: string,
  entries: Array<{ user_id: string; kind: CheckIn["kind"]; late?: boolean; location?: string }>,
): Promise<{ created: number; already: number }> {
  return requestWithAuth<{ created: number; already: number }>(
    `/api/v1/attendance/sessions/${sessionId}/bulk-checkin/`,
    { method: "POST", body: JSON.stringify({ entries }) },
  );
}

export function exportAttendanceCsvUrl(sessionId: string): string {
  return `${API_BASE_URL}/api/v1/attendance/sessions/${sessionId}/export.csv`;
}

// ---------------------------------------------------------------------------
// Student registrations (Phase 15 — per-(session, student) roster + QR).
//
// The EO populates a session's roster from the active STUDENT user pool;
// each row is what the security officer scans at the door. The QR PNG
// is fetched as a binary ``<img>`` and the row id is the URL payload
// (the scanner decodes the id and the backend resolves the row).
// ---------------------------------------------------------------------------
export type StudentRegistration = {
  id: string;
  session: string;
  student: string;
  student_email?: string;
  student_name?: string;
  student_code: string;
  created_at: string;
};

export const getStudentRegistrations = (
  params?: Record<string, string | number | undefined>,
) =>
  requestWithAuth<Paginated<StudentRegistration>>(
    `/api/v1/exams/registrations/${qs(params)}`,
  );

export async function createStudentRegistration(payload: {
  session: string;
  student: string;
  student_code: string;
}): Promise<StudentRegistration> {
  return requestWithAuth<StudentRegistration>("/api/v1/exams/registrations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteStudentRegistration(id: string): Promise<void> {
  await requestWithAuth<void>(`/api/v1/exams/registrations/${id}/`, {
    method: "DELETE",
  });
}

/**
 * URL of the printable QR PNG for a single registration row. The browser
 * uses it as an ``<img src>`` — the backend re-checks the read
 * permission (EO/HoD/SecOps/Invigilator) before serving the bytes.
 */
export function studentRegistrationQrUrl(id: string): string {
  return `${API_BASE_URL}/api/v1/exams/registrations/${id}/qr.png/`;
}

/**
 * Idempotent roster-populator for one session. The backend walks every
 * active STUDENT user and creates a :class:`StudentRegistration` row
 * per active student; a session that already has any registrations
 * is left alone (returns ``created: 0``).
 */
export async function populateRegistrations(
  sessionId: string,
): Promise<{ created: number }> {
  return requestWithAuth<{ created: number }>(
    `/api/v1/exams/registrations/sessions/${sessionId}/populate/`,
    { method: "POST" },
  );
}

/**
 * Security officer action — scan a student's QR (or type their
 * student_code fallback) to check them in. The backend resolves the
 * registration id, looks up the row, and runs the same
 * ``_upsert`` path as the bulk check-in. The ``signature_png`` is the
 * bare base64 from a canvas — no data-URL prefix.
 */
export async function scanStudent(
  sessionId: string,
  registrationId: string,
  opts?: { signature_png?: string; location?: string },
): Promise<CheckIn> {
  return requestWithAuth<CheckIn>("/api/v1/attendance/scan/", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      registration_id: registrationId,
      signature_png: opts?.signature_png ?? "",
      location: opts?.location ?? "",
    }),
  });
}

// ---------------------------------------------------------------------------
// Notifications (Phase 14 — the in-app event feed + topbar bell)
// ---------------------------------------------------------------------------
export type Notification = {
  id: string;
  kind: string;
  title: string;
  body: string;
  target_type: string;
  target_id: string;
  target_url: string;
  is_read: boolean;
  read_at: string | null;
  email_sent_at: string | null;
  email_failed: boolean;
  recipient_email: string;
  created_at: string;
};

export const getNotifications = (
  params?: Record<string, string | number | undefined>,
) =>
  requestWithAuth<Paginated<Notification>>(
    `/api/v1/notifications/${qs(params)}`,
  );

export async function markAllRead(): Promise<{ updated: number }> {
  return requestWithAuth<{ updated: number }>("/api/v1/notifications/mark-all-read/", {
    method: "POST",
  });
}

export async function markRead(id: string): Promise<Notification> {
  return requestWithAuth<Notification>(`/api/v1/notifications/${id}/read/`, {
    method: "POST",
  });
}

export async function getUnreadCount(): Promise<{ count: number }> {
  return requestWithAuth<{ count: number }>("/api/v1/notifications/unread-count/");
}

export function calendarFeedUrl(): string {
  return `${API_BASE_URL}/api/v1/calendar/feed.ics`;
}

/**
 * Per-session .ics URL (Phase 16). The backend resolves the session,
 * runs the same authorisation check as the per-session GET endpoint
 * (operations roles see any; INVIGILATOR needs a confirmed
 * allocation; STUDENT needs a StudentRegistration or the session
 * being in the public upcoming list), and returns a 1-event
 * VCALENDAR. Returns 404 (not 403) when the caller is not
 * authorised, to avoid leaking existence.
 */
export function calendarSessionUrl(sessionId: string): string {
  return `${API_BASE_URL}/api/v1/calendar/sessions/${sessionId}.ics`;
}

// Analytics (Phase 16)
export const getAnalyticsSummary = () =>
  requestWithAuth<AnalyticsSummary>("/api/v1/analytics/summary/");

// Rooms
export const getRooms = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Room>>(`/api/v1/rooms/rooms/${qs(params)}`);
export const getBuildings = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Building>>(`/api/v1/rooms/buildings/${qs(params)}`);

export type Building = {
  id: string;
  code: string;
  name: string;
  address?: string;
  room_count?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

// Reports
export const getReportExports = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<ReportExport>>(`/api/v1/reports/exports/${qs(params)}`);

export async function createReportExport(payload: {
  title: string;
  format: ReportExport["format"];
  audience?: ReportExport["audience"];
  cycle_id?: string;
  parameters?: Record<string, unknown>;
}): Promise<ReportExport> {
  return requestWithAuth<ReportExport>("/api/v1/reports/exports/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadReportExport(id: string): Promise<Blob> {
  const access = getStoredAccessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1/reports/exports/${id}/download/`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  return response.blob();
}

// ---------------------------------------------------------------------------
// Dashboard summary
// ---------------------------------------------------------------------------
/**
 * Aggregate the five numbers behind the operations dashboard into a
 * single object. Each sub-call is wrapped so a 200-with-empty-data
 * or a 5xx doesn't kill the whole summary — but a 401/403 (stale
 * JWT, recently-revoked role) DOES throw, so the dashboard can
 * surface a "your role doesn't allow this view" banner instead of
 * rendering a half-broken control room.
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  // The sub-call helper re-throws 401/403 so useFetch sees them. All
  // other failures (network error, 5xx, parsing) collapse to ``null``
  // — we'd rather show a degraded dashboard than a hard error.
  const safe = async <T>(p: Promise<T>): Promise<T | null> => {
    try {
      return await p;
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 401 || status === 403) throw err;
      return null;
    }
  };
  const [period, sessions, invigilators, runs, incidents, openIncidents] = await Promise.all([
    safe(getActiveExamPeriod()),
    safe(getExamSessions({ page_size: 5, ordering: "starts_at" })),
    safe(getInvigilators({ page_size: 1 })),
    safe(getAllocationRuns({ page_size: 5 })),
    safe(getIncidents({ page_size: 5 })),
    safe(getIncidents({ status: "open", page_size: 1 })),
  ]);
  return {
    active_period: period,
    total_sessions: sessions?.count ?? 0,
    total_invigilators: invigilators?.count ?? 0,
    total_incidents_open: openIncidents?.count ?? 0,
    recent_runs: runs?.results ?? [],
    upcoming_sessions: sessions?.results ?? [],
    recent_incidents: incidents?.results ?? [],
  };
}

// ---------------------------------------------------------------------------
// AI assistant
// ---------------------------------------------------------------------------
export type AiChatContext = {
  active_period: string | null;
  upcoming_session_count: number;
  open_conflict_count: number;
  open_incident_count: number;
  invigilator_total: number;
  invigilator_unavailable_today: number;
  latest_run_id: string | null;
  latest_run_coverage: number | null;
  generated_at: string;
};

export type AiChatReply = {
  reply: string;
  suggestions: string[];
  intent: string;
  context: AiChatContext;
};

/**
 * Ask the AI assistant a free-form question. The assistant is fed live
 * database data, so the reply is grounded in the actual state of the
 * cycle rather than hallucinated.
 */
export async function postAiChat(message: string): Promise<AiChatReply> {
  return requestWithAuth<AiChatReply>("/api/v1/ai/chat/", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// ---------------------------------------------------------------------------
// Audit log — every consequential mutation is written by signals; this is
// the read side. Filtered/paginated like the rest of the API.
// ---------------------------------------------------------------------------
export const getAuditLogs = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<AuditLog>>(`/api/v1/audit/${qs(params)}`);

// ---------------------------------------------------------------------------
// User management (admin only — backend gates with
// ``accounts.user.create`` / ``accounts.user.reset_password`` /
// ``accounts.role.assign``).
// ---------------------------------------------------------------------------
//
// The list endpoint returns a flat array, not DRF's paginated wrapper,
// so we type it as ``User[]`` directly. The backend's
// ``UserViewSet.list`` is a thin ``objects.all().order_by("email")``
// scan — fine for the seeded user counts, but we'll need real
// pagination + a search field if this ever grows past a few hundred
// users.
export async function getUsers(
  params?: Record<string, string | number | undefined>,
): Promise<User[]> {
  return requestWithAuth<User[]>(`/api/v1/users/${qs(params)}`);
}

export async function getUser(id: string): Promise<User> {
  return requestWithAuth<User>(`/api/v1/users/${id}/`);
}

export async function adminResetUserPassword(
  id: string,
  newPassword: string,
  confirmPassword: string,
): Promise<void> {
  await requestWithAuth<void>(`/api/v1/users/${id}/reset-password/`, {
    method: "POST",
    body: JSON.stringify({
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });
}

export async function setUserRoles(id: string, roleCodes: string[]): Promise<User> {
  return requestWithAuth<User>(`/api/v1/users/${id}/set-roles/`, {
    method: "POST",
    body: JSON.stringify({ roles: roleCodes }),
  });
}

export async function deleteUser(id: string): Promise<void> {
  await requestWithAuth<void>(`/api/v1/users/${id}/`, { method: "DELETE" });
}

export async function unlockUserAccount(id: string): Promise<void> {
  await requestWithAuth<void>(`/api/v1/users/${id}/unlock/`, { method: "POST" });
}

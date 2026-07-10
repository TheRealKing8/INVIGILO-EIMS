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
  refresh: string;
  access_lifetime_seconds?: number;
  refresh_lifetime_seconds?: number;
  user: AuthUser;
};

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
  reporter: string | null;
  reporter_email?: string | null;
  severity: "low" | "medium" | "high" | "critical";
  status: "open" | "investigating" | "escalated" | "resolved";
  reported_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
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
// Storage
// ---------------------------------------------------------------------------
const STORAGE_KEYS = {
  access: "invigilo_access_token",
  refresh: "invigilo_refresh_token",
  user: "invigilo_user",
} as const;

export function saveAuthTokens(
  accessToken: string,
  refreshToken: string,
  user?: AuthUser,
) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.access, accessToken);
  localStorage.setItem(STORAGE_KEYS.refresh, refreshToken);
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

export function getStoredRefreshToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.refresh);
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
  localStorage.removeItem(STORAGE_KEYS.refresh);
  localStorage.removeItem(STORAGE_KEYS.user);
}

// ---------------------------------------------------------------------------
// Core request — adds Authorization header from storage.
// On 401, attempts a single refresh; on second 401, clears tokens and
// throws. The 401 callback (passed in by the client) handles redirecting
// to /login so server-rendered routes don't end up in a redirect loop.
// ---------------------------------------------------------------------------
let onUnauthenticated: (() => void) | null = null;
export function setOnUnauthenticated(cb: () => void) {
  onUnauthenticated = cb;
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
    if (status !== 401 || !access) {
      throw err;
    }
    // Try a refresh.
    const refresh = getStoredRefreshToken();
    if (!refresh) {
      clearAuthTokens();
      onUnauthenticated?.();
      throw err;
    }
    try {
      const tokens = await rawRequest<{ access: string; refresh?: string }>(
        "/api/v1/auth/refresh/",
        { method: "POST", body: JSON.stringify({ refresh }) },
      );
      saveAuthTokens(tokens.access, tokens.refresh ?? refresh);
      // Retry once.
      return await rawRequest<T>(path, init, tokens.access);
    } catch (refreshErr) {
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
): Promise<AuthTokens> {
  return request<AuthTokens>("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
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

export async function logoutRequest(refreshToken: string): Promise<void> {
  await request<void>("/api/v1/auth/logout/", {
    method: "POST",
    body: JSON.stringify({ refresh: refreshToken }),
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
export const getExamPeriods = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<ExamPeriod>>(`/api/v1/exams/periods/${qs(params)}`);
export const getActiveExamPeriod = () =>
  requestWithAuth<Paginated<ExamPeriod>>(
    `/api/v1/exams/periods/${qs({ is_active: "true", page_size: 1 })}`,
  ).then((p) => p.results[0] ?? null);

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

// Allocations
export const getAllocations = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<Allocation>>(`/api/v1/allocations/allocations/${qs(params)}`);
export const getAllocationRuns = (params?: Record<string, string | number | undefined>) =>
  requestWithAuth<Paginated<AllocationRun>>(`/api/v1/allocations/runs/${qs(params)}`);
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
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const [period, sessions, invigilators, runs, incidents, openIncidents] = await Promise.all([
    getActiveExamPeriod().catch(() => null),
    getExamSessions({ page_size: 5, ordering: "starts_at" }).catch(() => null),
    getInvigilators({ page_size: 1 }).catch(() => null),
    getAllocationRuns({ page_size: 5 }).catch(() => null),
    getIncidents({ page_size: 5 }).catch(() => null),
    getIncidents({ status: "open", page_size: 1 }).catch(() => null),
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

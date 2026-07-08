const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type AuthUser = {
  id: string;
  email: string;
  full_name?: string;
  primary_role?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof data === "string"
        ? data
        : data?.detail || data?.message || "Request failed";
    throw new Error(message);
  }

  return data as T;
}

export async function getHealth() {
  return request<{ status: string; db: string; redis: string; migrations: string }>("/api/health/");
}

export async function loginWithEmailPassword(email: string, password: string) {
  return request<{
    access: string;
    refresh: string;
    user: {
      id: string;
      email: string;
      full_name?: string;
      primary_role?: string;
    };
  }>("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}
export async function registerWithEmailPassword(fullName: string, email: string, password: string) {
  return request<{
    access: string;
    refresh: string;
    user: {
      id: string;
      email: string;
      full_name?: string;
      primary_role?: string;
    };
  }>('/api/v1/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
}
export async function getProfile(accessToken: string) {
  return request<{
    id: string;
    email: string;
    full_name?: string;
    primary_role?: string;
  }>("/api/v1/auth/me/", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function saveAuthTokens(accessToken: string, refreshToken: string, user?: AuthUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem("invigilo_access_token", accessToken);
  localStorage.setItem("invigilo_refresh_token", refreshToken);
  if (user) {
    localStorage.setItem("invigilo_user", JSON.stringify(user));
  } else {
    localStorage.removeItem("invigilo_user");
  }
}

export function getStoredAccessToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("invigilo_access_token");
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  const rawUser = localStorage.getItem("invigilo_user");
  if (!rawUser) return null;

  try {
    return JSON.parse(rawUser) as AuthUser;
  } catch {
    return null;
  }
}

export function clearAuthTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("invigilo_access_token");
  localStorage.removeItem("invigilo_refresh_token");
  localStorage.removeItem("invigilo_user");
}

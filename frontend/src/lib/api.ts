// ─────────────────────────────────────────────────────────────────────────────
// EduVerse — Centralized API Client
// Typed fetch wrappers with automatic Bearer JWT injection.
// Base URL is read from NEXT_PUBLIC_API_URL (defaults to http://localhost:8000).
// ─────────────────────────────────────────────────────────────────────────────

import type { APIError } from "./types";

// ─── Config ──────────────────────────────────────────────────────────────────

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

// ─── Token Store ─────────────────────────────────────────────────────────────
// Token is managed by auth-context, but api.ts needs it synchronously.
// We read from localStorage directly so api.ts has zero circular deps.

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("eduverse_jwt");
}

// ─── Request Helpers ─────────────────────────────────────────────────────────

function buildHeaders(extra?: HeadersInit, isMultipart = false): Headers {
  const headers = new Headers(extra);
  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!isMultipart) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }
  return url.toString();
}

// ─── Error Handling ───────────────────────────────────────────────────────────

export class APIClientError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code?: string
  ) {
    super(`[${status}] ${detail}`);
    this.name = "APIClientError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    let code: string | undefined;
    try {
      const body: APIError = await res.json();
      detail = body.detail ?? detail;
      code = body.code;
    } catch {
      // ignore JSON parse errors on error responses
    }
    throw new APIClientError(res.status, detail, code);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }

  // For file downloads (e.g. DPO export)
  return res.blob() as unknown as T;
}

// ─── Core Fetch Methods ───────────────────────────────────────────────────────

export async function apiGet<T>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    method: "GET",
    headers: buildHeaders(),
  });
  return handleResponse<T>(res);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  params?: Record<string, string>
): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    method: "POST",
    headers: buildHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiDelete<T = void>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    method: "DELETE",
    headers: buildHeaders(),
  });
  return handleResponse<T>(res);
}

export async function apiPatch<T>(
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "PATCH",
    headers: buildHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

// ─── Multipart Upload ─────────────────────────────────────────────────────────

export async function apiUpload<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: buildHeaders(undefined, true), // no Content-Type — let browser set boundary
    body: formData,
  });
  return handleResponse<T>(res);
}

// ─── Convenience: API endpoint namespaces ────────────────────────────────────
// Pre-built typed callers so components don't hardcode paths.

import type {
  GuestLoginResponse,
  AuthStatus,
  UnifiedCourse,
  CreateCourseRequest,
  Coursework,
  IngestedFile,
  IngestionStatus,
  ClassroomItem,
  ChatSession,
  SessionDetail,
  FeedbackRequest,
  ProfileResponse,
  KnowledgeUniverseResponse,
  RLStats,
  RLDashboard,
  RLModel,
  RLEpisode,
  TrainingStatus,
} from "./types";

// Auth
export const authApi = {
  loginGuest: () =>
    apiPost<GuestLoginResponse>("/api/v1/auth/login/guest"),
  loginGoogleUrl: () =>
    `${BASE_URL}/api/v1/auth/login/google`,
  status: () =>
    apiGet<AuthStatus>("/api/v1/auth/status"),
  disconnect: () =>
    apiDelete("/api/v1/auth/disconnect"),
  wipe: () =>
    apiPost("/api/v1/auth/wipe"),
};

// Courses
export const coursesApi = {
  list: () =>
    apiGet<UnifiedCourse[]>("/api/v1/courses/"),
  create: (body: CreateCourseRequest) =>
    apiPost<UnifiedCourse>("/api/v1/courses/", body),
  delete: (courseId: string) =>
    apiDelete(`/api/v1/courses/${courseId}`),
  coursework: (courseId: string) =>
    apiGet<Coursework[]>(`/api/v1/courses/${courseId}/coursework`),
};

// Ingestion
export const ingestionApi = {
  trigger: (courseId: string, selectedItemIds?: string[]) =>
    apiPost("/api/v1/ingestion/", {
      course_id: courseId,
      ...(selectedItemIds ? { selected_item_ids: selectedItemIds } : {}),
    }),
  sync: (courseId: string) =>
    apiPost("/api/v1/ingestion/sync", { course_id: courseId }),
  status: (courseId: string) =>
    apiGet<IngestionStatus>(`/api/v1/ingestion/status/${courseId}`),
  files: (courseId: string) =>
    apiGet<IngestedFile[]>(`/api/v1/ingestion/${courseId}/files`),
  courseworkFiles: (courseId: string) =>
    apiGet<ClassroomItem[]>(`/api/v1/ingestion/${courseId}/coursework-files`),
  upload: (formData: FormData) =>
    apiUpload("/api/v1/ingestion/upload", formData),
  deleteIndex: (courseId: string) =>
    apiDelete(`/api/v1/ingestion/${courseId}`),
  deleteFile: (courseId: string, filename: string) =>
    apiDelete(`/api/v1/ingestion/${courseId}/files/${encodeURIComponent(filename)}`),
};

// Sessions
export const sessionsApi = {
  list: (courseId: string) =>
    apiGet<ChatSession[]>("/api/v1/sessions/", { course_id: courseId }),
  get: (sessionId: string) =>
    apiGet<SessionDetail>(`/api/v1/sessions/${sessionId}`),
  delete: (sessionId: string) =>
    apiDelete(`/api/v1/sessions/${sessionId}`),
  rename: (sessionId: string, title: string) =>
    apiPatch<ChatSession>(`/api/v1/sessions/${sessionId}`, { title }),
};

// Feedback
export const feedbackApi = {
  submit: (sessionId: string, messageId: string, body: FeedbackRequest) =>
    apiPost(`/api/v1/chat/${sessionId}/messages/${messageId}/feedback`, {
      // Backend expects `is_positive: bool`, not `rating: "up"|"down"`
      is_positive: body.rating === "up",
      comment: body.comment ?? null,
    }),
};

// Cache
export const cacheApi = {
  clear: (courseId: string) =>
    apiDelete(`/api/v1/cache/${courseId}`),
};

// Profile
export const profileApi = {
  get: () =>
    apiGet<ProfileResponse>("/api/v1/profile/"),
  universe: () =>
    apiGet<KnowledgeUniverseResponse>("/api/v1/profile/mastery/universe"),
};

// RL / Admin
export const rlApi = {
  stats: () =>
    apiGet<RLStats>("/api/v1/rl/stats"),
  dashboard: () =>
    apiGet<RLDashboard>("/api/v1/rl/dashboard"),
  models: () =>
    apiGet<RLModel[]>("/api/v1/rl/models"),
  episodes: () =>
    apiGet<RLEpisode[]>("/api/v1/rl/episodes"),
  exportDpo: () =>
    `${BASE_URL}/api/v1/rl/dpo/export`,
  triggerTraining: () =>
    apiPost("/api/v1/rl/train/trigger"),
  distill: () =>
    apiPost("/api/v1/rl/train/distill"),
  trainingStatus: () =>
    apiGet<TrainingStatus>("/api/v1/rl/train/status"),
};

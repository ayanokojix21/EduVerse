import { getSession } from "next-auth/react";
import { type Session } from "next-auth";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthToken(providedSession?: Session | null): Promise<string | null> {
  // If running on the client, or if session is omitted, fetch it implicitly for the client
  if (typeof window !== "undefined") {
    const session = providedSession || await getSession();
    return (session as any)?.app_jwt || null;
  }
  return (providedSession as any)?.app_jwt || null;
}

interface FetchOptions extends RequestInit {
  session?: Session | null;
}

/**
 * Core authenticated fetch wrapper
 */
export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { session, ...customConfig } = options;
  const token = await getAuthToken(session);

  const headers: HeadersInit = {};

  // Only set Content-Type for non-multipart requests
  if (!options.body || typeof options.body === 'string') {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    ...customConfig,
    headers: {
      ...headers,
      ...customConfig.headers,
    },
  };

  const response = await fetch(`${API_URL}${endpoint}`, config);

  if (!response.ok) {
    let errorDetail = "API Error";
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignored
    }
    throw new Error(`[${response.status}] ${errorDetail}`);
  }

  // Handle empty responses
  const text = await response.text();
  return text ? JSON.parse(text) : ({} as T);
}

// ── Common API Services ────────────────────────────────────────

export const api = {
  auth: {
    getStatus: (session?: Session | null) => 
      apiFetch<{ user_id: string; authenticated: boolean; user?: any }>('/auth/status', { session }),
    disconnect: (session?: Session | null) => 
      apiFetch<{ disconnected: boolean }>('/auth/disconnect', { method: 'DELETE', session }),
  },
  courses: {
    list: (session?: Session | null) => 
      apiFetch<any[]>('/courses', { session }),
    getCoursework: (courseId: string, session?: Session | null) => 
      apiFetch<any>(`/courses/${courseId}/coursework`, { session }),
  },
  profile: {
    get: (session?: Session | null) => 
      apiFetch<any>('/profile', { session }),
  },
  ingestion: {
    trigger: (courseId: string, forceRefresh = false, session?: Session | null) =>
      apiFetch<{ status: string; message: string; course_id: string }>('/ingest', {
        method: 'POST',
        body: JSON.stringify({ course_id: courseId, force_refresh: forceRefresh }),
        session,
      }),
    sync: (courseId: string, session?: Session | null) =>
      apiFetch<any>('/ingest/sync', {
        method: 'POST',
        body: JSON.stringify({ course_id: courseId }),
        session,
      }),
    deleteIndex: (courseId: string, session?: Session | null) =>
      apiFetch<{ success: boolean; course_id: string; message: string }>(`/ingest/${courseId}`, {
        method: 'DELETE',
        session,
      }),
    deleteFile: (courseId: string, filename: string, session?: Session | null) =>
      apiFetch<any>(`/ingest/${courseId}/files/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        session,
      }),
    getStatus: (courseId: string, session?: Session | null) =>
      apiFetch<any>(`/ingest/status/${courseId}`, { session }),
    listFiles: (courseId: string, session?: Session | null) =>
      apiFetch<any[]>(`/ingest/${courseId}/files`, { session }),
    uploadFile: (courseId: string, file: File, session?: Session | null) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch<any>(`/ingest/upload?course_id=${courseId}`, {
        method: 'POST',
        body: formData,
        session,
      });
    },
  },
  sessions: {
    list: (courseId: string, session?: Session | null) =>
      apiFetch<any[]>(`/sessions?course_id=${courseId}`, { session }),
    get: (sessionId: string, session?: Session | null) =>
      apiFetch<any>(`/sessions/${sessionId}`, { session }),
    delete: (sessionId: string, session?: Session | null) =>
      apiFetch<any>(`/sessions/${sessionId}`, { method: 'DELETE', session }),
    rename: (sessionId: string, title: string, session?: Session | null) =>
      apiFetch<any>(`/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
        session,
      }),
  },
};

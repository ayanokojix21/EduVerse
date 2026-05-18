// ─────────────────────────────────────────────────────────────────────────────
// EduVerse — POST-based SSE Stream Helper
// Uses @microsoft/fetch-event-source to support POST requests with SSE.
// Handles all 10 chat event types with typed callbacks.
// ─────────────────────────────────────────────────────────────────────────────

import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { SSEEventMap, ChatRequest, HITLResumeRequest } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("eduverse_jwt");
}

// ─── SSE Callback Types ───────────────────────────────────────────────────────

export type SSECallbacks = {
  [K in keyof SSEEventMap]?: (data: SSEEventMap[K]) => void;
} & {
  onOpen?: () => void;
  onClose?: () => void;
  onRawError?: (err: Error) => void;
};

// ─── AbortController wrapper ──────────────────────────────────────────────────

export interface SSEConnection {
  abort: () => void;
}

// ─── Core SSE Connector ───────────────────────────────────────────────────────

function connectSSE(
  path: string,
  body: unknown,
  callbacks: SSECallbacks
): SSEConnection {
  const controller = new AbortController();
  const token = getToken();
  // Track whether the stream ended intentionally (done / abort)
  // so we can prevent fetchEventSource from auto-retrying.
  let streamFinished = false;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  fetchEventSource(`${BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: controller.signal,

    async onopen(response) {
      if (!response.ok) {
        streamFinished = true;
        throw new Error(`SSE connection failed: ${response.status}`);
      }
      callbacks.onOpen?.();
    },

    onmessage(ev) {
      if (!ev.event || !ev.data) return;

      let parsed: unknown;
      try {
        parsed = JSON.parse(ev.data);
      } catch {
        console.warn("[SSE] Failed to parse event data:", ev.data);
        return;
      }

      const event = ev.event as keyof SSEEventMap;

      switch (event) {
        case "status":
          callbacks.status?.(parsed as SSEEventMap["status"]);
          break;
        case "node_start":
          callbacks.node_start?.(parsed as SSEEventMap["node_start"]);
          break;
        case "node_end":
          callbacks.node_end?.(parsed as SSEEventMap["node_end"]);
          break;
        case "tool_start":
          callbacks.tool_start?.(parsed as SSEEventMap["tool_start"]);
          break;
        case "tool_end":
          callbacks.tool_end?.(parsed as SSEEventMap["tool_end"]);
          break;
        case "retrieval_label":
          callbacks.retrieval_label?.(parsed as SSEEventMap["retrieval_label"]);
          break;
        case "agent_thought":
          callbacks.agent_thought?.(parsed as SSEEventMap["agent_thought"]);
          break;
        case "token":
          callbacks.token?.(parsed as SSEEventMap["token"]);
          break;
        case "done":
          // Mark finished BEFORE calling the callback so that if onclose
          // fires synchronously after this, it won't retry.
          streamFinished = true;
          callbacks.done?.(parsed as SSEEventMap["done"]);
          break;
        case "error":
          streamFinished = true;
          callbacks.error?.(parsed as SSEEventMap["error"]);
          break;
        case "hitl":
          // HITL pauses the stream — mark finished to block retry.
          streamFinished = true;
          callbacks.hitl?.(parsed as SSEEventMap["hitl"]);
          break;
        default:
          console.warn("[SSE] Unknown event type:", event);
      }
    },

    onclose() {
      callbacks.onClose?.();
      // fetchEventSource retries when onclose is reached without a
      // preceding error. Throw to prevent that — the backend
      // intentionally closes the stream after 'done'.
      if (!streamFinished) {
        // Unexpected close — still don't retry, just surface as an error.
        callbacks.onRawError?.(new Error("SSE stream closed unexpectedly"));
      }
      throw new Error("SSE stream ended — no retry");
    },

    onerror(err) {
      if (controller.signal.aborted) {
        // User-initiated abort — do not call error callback or retry.
        throw err;
      }
      callbacks.onRawError?.(err instanceof Error ? err : new Error(String(err)));
      // Throw to prevent fetchEventSource from retrying automatically.
      throw err;
    },
  });

  return { abort: () => { streamFinished = true; controller.abort(); } };
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Start a new chat stream (new or continue existing session).
 * Returns an SSEConnection with an `abort()` method.
 */
export function startChatStream(
  request: ChatRequest,
  callbacks: SSECallbacks
): SSEConnection {
  return connectSSE("/api/v1/chat/stream", request, callbacks);
}

/**
 * Resume a paused HITL conversation.
 * Returns an SSEConnection with an `abort()` method.
 */
export function resumeChatStream(
  request: HITLResumeRequest,
  callbacks: SSECallbacks
): SSEConnection {
  return connectSSE("/api/v1/chat/stream/resume", request, callbacks);
}

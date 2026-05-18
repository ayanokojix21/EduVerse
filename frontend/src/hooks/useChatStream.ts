"use client";

// ─────────────────────────────────────────────────────────────────────────────
// useChatStream — useReducer-based state machine for SSE chat streaming.
// States: idle → connecting → streaming → hitl_paused → done → error
// Handles all 10 SSE event types from the backend.
// ─────────────────────────────────────────────────────────────────────────────

import { useCallback, useReducer, useRef } from "react";
import {
  startChatStream,
  resumeChatStream,
  type SSEConnection,
} from "@/lib/sse";
import { sessionsApi, feedbackApi } from "@/lib/api";
import type {
  ChatMessage,
  ChatRequest,
  HITLResumeRequest,
  AgentThought,
  DonePayload,
} from "@/lib/types";

// ─── State ────────────────────────────────────────────────────────────────────

export type StreamStatus =
  | "idle"
  | "connecting"
  | "streaming"
  | "hitl_paused"
  | "done"
  | "error";

export interface ChatState {
  status: StreamStatus;
  messages: ChatMessage[];
  sessionId: string | null;
  // Streaming accumulator
  streamingText: string;
  // Observability
  activeNodes: string[];
  activeTools: string[];
  agentThoughts: AgentThought[];
  retrievalLabel: string | null;
  retrievalMs: number | null;
  mermaidGraph: string | null;
  traceUrl: string | null;
  critic: Record<string, unknown> | null;
  // Status messages from backend
  statusMessage: string | null;
  // Error
  errorMessage: string | null;
  errorCode: string | null;
}

// ─── Actions ──────────────────────────────────────────────────────────────────

type ChatAction =
  | { type: "CONNECT" }
  | { type: "SET_SESSION_ID"; sessionId: string }
  | { type: "ADD_USER_MESSAGE"; message: ChatMessage }
  | { type: "LOAD_HISTORY"; messages: ChatMessage[]; sessionId: string }
  | { type: "SSE_STATUS"; message: string; session_id: string }
  | { type: "SSE_NODE_START"; node: string; message: string }
  | { type: "SSE_NODE_END"; node: string }
  | { type: "SSE_TOOL_START"; tool: string; input: unknown }
  | { type: "SSE_TOOL_END"; tool: string }
  | {
      type: "SSE_RETRIEVAL_LABEL";
      label: string;
      top_score: number;
      confidence_label: string;
      retrieval_ms: number;
    }
  | { type: "SSE_AGENT_THOUGHT"; thought: AgentThought }
  | { type: "SSE_TOKEN"; text: string }
  | { type: "SSE_DONE"; payload: DonePayload }
  | { type: "SSE_ERROR"; message: string; code: string }
  | { type: "SSE_CLOSE" }
  | { type: "HITL_PAUSE" }
  | { type: "RESET" }
  | { type: "SET_FEEDBACK"; messageId: string; rating: "up" | "down" | null };

// ─── Initial State ────────────────────────────────────────────────────────────

const initialState: ChatState = {
  status: "idle",
  messages: [],
  sessionId: null,
  streamingText: "",
  activeNodes: [],
  activeTools: [],
  agentThoughts: [],
  retrievalLabel: null,
  retrievalMs: null,
  mermaidGraph: null,
  traceUrl: null,
  critic: null,
  statusMessage: null,
  errorMessage: null,
  errorCode: null,
};

// ─── Reducer ──────────────────────────────────────────────────────────────────

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "CONNECT":
      return {
        ...state,
        status: "connecting",
        streamingText: "",
        activeNodes: [],
        activeTools: [],
        agentThoughts: [],
        retrievalLabel: null,
        retrievalMs: null,
        mermaidGraph: null,
        traceUrl: null,
        critic: null,
        statusMessage: null,
        errorMessage: null,
        errorCode: null,
      };

    case "SET_SESSION_ID":
      return { ...state, sessionId: action.sessionId };

    case "ADD_USER_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };

    case "LOAD_HISTORY":
      return {
        ...state,
        messages: action.messages,
        sessionId: action.sessionId,
        status: "done",
      };

    case "SSE_STATUS":
      return {
        ...state,
        status: "streaming",
        statusMessage: action.message,
        sessionId: action.session_id || state.sessionId,
      };

    case "SSE_NODE_START":
      return {
        ...state,
        status: "streaming",
        activeNodes: [...state.activeNodes, action.node],
        statusMessage: action.message,
      };

    case "SSE_NODE_END":
      return {
        ...state,
        activeNodes: state.activeNodes.filter((n) => n !== action.node),
      };

    case "SSE_TOOL_START":
      return {
        ...state,
        activeTools: [...state.activeTools, action.tool],
      };

    case "SSE_TOOL_END":
      return {
        ...state,
        activeTools: state.activeTools.filter((t) => t !== action.tool),
      };

    case "SSE_RETRIEVAL_LABEL":
      return {
        ...state,
        retrievalLabel: action.label,
        retrievalMs: action.retrieval_ms,
      };

    case "SSE_AGENT_THOUGHT":
      return {
        ...state,
        agentThoughts: [...state.agentThoughts, action.thought],
      };

    case "SSE_TOKEN":
      return {
        ...state,
        status: "streaming",
        streamingText: state.streamingText + action.text,
      };

    case "SSE_DONE": {
      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}`,
        role: "assistant",
        content: action.payload.response,
        citations: action.payload.citations,
        retrieval_label: action.payload.retrieval_label,
        agent_thoughts: action.payload.agent_thoughts,
        mermaid_graph: action.payload.mermaid_graph,
        trace_url: action.payload.trace_url,
        retrieval_ms: action.payload.retrieval_ms,
        created_at: new Date().toISOString(),
        feedback: null,
      };

      return {
        ...state,
        status: "done",
        messages: [...state.messages, assistantMessage],
        streamingText: "",
        sessionId: action.payload.session_id || state.sessionId,
        mermaidGraph: action.payload.mermaid_graph,
        traceUrl: action.payload.trace_url,
        critic: action.payload.critic,
        agentThoughts: action.payload.agent_thoughts,
        retrievalLabel: action.payload.retrieval_label,
        retrievalMs: action.payload.retrieval_ms,
      };
    }

    case "SSE_ERROR":
      return {
        ...state,
        status: "error",
        errorMessage: action.message,
        errorCode: action.code,
        streamingText: "",
      };

    case "SSE_CLOSE":
      return {
        ...state,
        status: state.status === "streaming" ? "done" : state.status,
        streamingText: "",
      };

    case "HITL_PAUSE":
      return { ...state, status: "hitl_paused" };

    case "RESET":
      return { ...initialState };

    case "SET_FEEDBACK":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.messageId ? { ...m, feedback: action.rating } : m
        ),
      };

    default:
      return state;
  }
}

// ─── SSE Callback Wiring (shared between send and resume) ─────────────────────

function buildCallbacks(dispatch: React.Dispatch<ChatAction>) {
  return {
    onOpen: () => {},
    status: (data: { message: string; session_id: string }) =>
      dispatch({ type: "SSE_STATUS", ...data }),
    node_start: (data: { node: string; message: string }) =>
      dispatch({ type: "SSE_NODE_START", ...data }),
    node_end: (data: { node: string }) =>
      dispatch({ type: "SSE_NODE_END", ...data }),
    tool_start: (data: { tool: string; input: unknown }) =>
      dispatch({ type: "SSE_TOOL_START", ...data }),
    tool_end: (data: { tool: string }) =>
      dispatch({ type: "SSE_TOOL_END", ...data }),
    retrieval_label: (data: {
      label: string;
      top_score: number;
      confidence_label: string;
      retrieval_ms: number;
    }) => dispatch({ type: "SSE_RETRIEVAL_LABEL", ...data }),
    agent_thought: (data: AgentThought) =>
      dispatch({ type: "SSE_AGENT_THOUGHT", thought: data }),
    token: (data: { text: string }) =>
      dispatch({ type: "SSE_TOKEN", ...data }),
    done: (data: DonePayload) =>
      dispatch({ type: "SSE_DONE", payload: data }),
    error: (data: { message: string; code: string }) =>
      dispatch({ type: "SSE_ERROR", ...data }),
    hitl: (data: { session_id: string; interrupt_data: any; trace_url: string }) =>
      dispatch({ type: "HITL_PAUSE" }),
    onClose: () => dispatch({ type: "SSE_CLOSE" }),
    onRawError: (err: Error) =>
      dispatch({
        type: "SSE_ERROR",
        message: err.message,
        code: "CONNECTION_ERROR",
      }),
  };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useChatStream(courseId: string) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const connectionRef = useRef<SSEConnection | null>(null);
  // Keep sessionId in a ref so callbacks don't need it in their dep arrays.
  // This prevents sendMessage/resumeHITL from being recreated on every SSE event.
  const sessionIdRef = useRef<string | null>(null);
  if (state.sessionId !== sessionIdRef.current) {
    sessionIdRef.current = state.sessionId;
  }


  // ── Send a new message ────────────────────────────────────────────────────

  const sendMessage = useCallback(
    (text: string, imageData?: string, imageMimetype?: string) => {
      const userMessage: ChatMessage = {
        id: `user_${Date.now()}`,
        role: "user",
        content: text,
        image_data: imageData,
        image_mimetype: imageMimetype,
        created_at: new Date().toISOString(),
        feedback: null,
      };
      dispatch({ type: "ADD_USER_MESSAGE", message: userMessage });
      dispatch({ type: "CONNECT" });

      const request: ChatRequest = {
        message: text,
        course_id: courseId,
        session_id: sessionIdRef.current ?? undefined,
        image_data: imageData,
        image_mimetype: imageMimetype,
      };

      connectionRef.current?.abort();
      connectionRef.current = startChatStream(request, buildCallbacks(dispatch));
    },
    [courseId]  // sessionId read from ref — stable
  );

  // ── Resume HITL ───────────────────────────────────────────────────────────

  const resumeHITL = useCallback(
    (decision: "search_web" | "socratic_only") => {
      if (!sessionIdRef.current) return;
      dispatch({ type: "CONNECT" });

      const request: HITLResumeRequest = {
        session_id: sessionIdRef.current,
        decision,
      };

      connectionRef.current?.abort();
      connectionRef.current = resumeChatStream(
        request,
        buildCallbacks(dispatch)
      );
    },
    []  // sessionId read from ref — stable
  );

  // ── Load session history ──────────────────────────────────────────────────

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const detail = await sessionsApi.get(sessionId);
      dispatch({
        type: "LOAD_HISTORY",
        messages: detail.messages,
        sessionId,
      });
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  }, []);

  // ── Submit feedback ───────────────────────────────────────────────────────

  const submitFeedback = useCallback(
    async (messageId: string, rating: "up" | "down", comment?: string) => {
      if (!sessionIdRef.current) return;
      dispatch({ type: "SET_FEEDBACK", messageId, rating });
      try {
        await feedbackApi.submit(sessionIdRef.current, messageId, {
          rating,
          comment,
        });
      } catch (err) {
        console.error("Failed to submit feedback:", err);
        dispatch({ type: "SET_FEEDBACK", messageId, rating: null });
      }
    },
    []  // sessionId read from ref — stable
  );

  // ── Abort ─────────────────────────────────────────────────────────────────

  const abort = useCallback(() => {
    connectionRef.current?.abort();
    connectionRef.current = null;
  }, []);

  // ── Reset (new chat) ─────────────────────────────────────────────────────

  const reset = useCallback(() => {
    connectionRef.current?.abort();
    connectionRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  return {
    ...state,
    sendMessage,
    resumeHITL,
    loadSession,
    submitFeedback,
    abort,
    reset,
  };
}

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ChatStream — Renders the scrollable message list.
//
// Responsibilities:
// - Render all ChatMessage objects via MessageBubble
// - Auto-scroll to bottom on new messages / streaming tokens
// - Show empty state when no messages exist
// - Show status indicator during connecting/streaming
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, memo } from "react";
import type { ChatMessage } from "@/lib/types";
import type { StreamStatus } from "@/hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ChatStreamProps {
  messages: ChatMessage[];
  status: StreamStatus;
  statusMessage: string | null;
  streamingText: string;
  onFeedback?: (messageId: string, rating: "up" | "down") => void;
}

// ─── Status Bar ──────────────────────────────────────────────────────────────

function StatusIndicator({
  status,
  statusMessage,
}: {
  status: StreamStatus;
  statusMessage: string | null;
}) {
  if (status === "idle" || status === "done") return null;

  const isActive = status === "connecting" || status === "streaming";
  const isError = status === "error";

  return (
    <div
      className={`
        flex items-center gap-2 px-4 py-2 mx-auto
        text-[12px] rounded-full w-fit
        animate-[fade-in_0.2s_ease-out]
        ${
          isError
            ? "bg-[var(--color-danger-dim)] text-[var(--color-danger)]"
            : isActive
            ? "bg-[rgba(239,243,244,0.04)] text-[var(--color-text-muted)]"
            : "bg-[var(--color-warning-dim)] text-[var(--color-warning)]"
        }
      `}
    >
      {isActive && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-[pulse-fast_0.8s_ease-in-out_infinite]" />
      )}
      {statusMessage ?? (
        status === "connecting"
          ? "Connecting…"
          : status === "streaming"
          ? "Thinking…"
          : status === "hitl_paused"
          ? "Waiting for your decision…"
          : status === "error"
          ? "Something went wrong"
          : ""
      )}
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-4 text-center px-6 animate-[fade-in_0.5s_ease-out]">
      <div
        className="
          w-16 h-16 rounded-full
          bg-gradient-to-br from-[rgba(239,243,244,0.08)] to-[rgba(239,243,244,0.02)]
          flex items-center justify-center
          text-[28px]
        "
      >
        ✦
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-[17px] font-semibold text-[var(--color-text-main)]">
          Ask anything about your course
        </h3>
        <p className="text-[13px] text-[var(--color-text-muted)] max-w-[320px]">
          EduVerse will search your course materials, reason through the answer, and cite its sources.
        </p>
      </div>

      {/* Suggestion chips */}
      <div className="flex flex-wrap justify-center gap-2 mt-2 max-w-[420px]">
        {[
          "Summarize the key concepts",
          "Help me with the assignment",
          "Explain this topic simply",
        ].map((s) => (
          <span
            key={s}
            className="
              text-[12px] text-[var(--color-text-muted)]
              px-3 py-1.5 rounded-full
              border border-[var(--color-border)]
              hover:bg-[rgba(239,243,244,0.04)]
              hover:text-[var(--color-text-main)]
              transition-colors duration-150
              cursor-default
            "
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export const ChatStream = memo(function ChatStream({
  messages,
  status,
  statusMessage,
  streamingText,
  onFeedback,
}: ChatStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when messages change or streaming text updates
  useEffect(() => {
    const el = bottomRef.current;
    if (!el) return;

    // Only auto-scroll if user is near the bottom (within 150px)
    const container = containerRef.current;
    if (container) {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
      if (isNearBottom) {
        el.scrollIntoView({ behavior: "smooth", block: "end" });
      }
    }
  }, [messages, streamingText]);

  // Prepare messages — inject streaming text into the last assistant message
  const displayMessages = messages.map((msg, i) => {
    if (
      i === messages.length - 1 &&
      msg.role === "assistant" &&
      msg.is_streaming &&
      streamingText
    ) {
      return { ...msg, content: streamingText };
    }
    return msg;
  });

  const isEmpty = displayMessages.length === 0 && status === "idle";

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto"
      id="chat-stream-container"
    >
      <div className="flex flex-col max-w-[720px] mx-auto px-4 py-6 min-h-full">
        {isEmpty ? (
          <EmptyState />
        ) : (
          <div className="flex flex-col gap-6 flex-1">
            {displayMessages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onFeedback={onFeedback}
              />
            ))}
          </div>
        )}

        {/* Status indicator */}
        {status !== "idle" && status !== "done" && (
          <div className="mt-4 mb-2">
            <StatusIndicator status={status} statusMessage={statusMessage} />
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} className="h-px" />
      </div>
    </div>
  );
});

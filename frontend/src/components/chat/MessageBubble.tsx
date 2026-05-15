"use client";

// ─────────────────────────────────────────────────────────────────────────────
// MessageBubble — Renders a single chat message (user or assistant).
//
// User messages:  right-aligned, panel bg (#16181C), rounded bubble.
// AI messages:    left-aligned, transparent bg, full-width with markdown prose.
//
// Includes:
// - Markdown rendering via react-markdown + rehype-raw + remark-gfm
// - Streaming cursor when `is_streaming` is true
// - Inline citation pills
// - 👍/👎 feedback buttons on AI messages
// - Optional image preview for multimodal messages
// ─────────────────────────────────────────────────────────────────────────────

import { memo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import type { ChatMessage, Citation } from "@/lib/types";
import { StreamingCursor } from "./StreamingCursor";
import { CitationPill } from "./CitationPill";

// ─── Props ───────────────────────────────────────────────────────────────────

interface MessageBubbleProps {
  message: ChatMessage;
  onFeedback?: (messageId: string, rating: "up" | "down") => void;
}

// ─── Citation Shelf ──────────────────────────────────────────────────────────

function CitationShelf({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-[var(--color-border)]">
      <span className="text-[11px] text-[var(--color-text-dim)] mr-1">Sources:</span>
      {citations.map((c) => (
        <CitationPill key={c.source_index} citation={c} />
      ))}
    </div>
  );
}

// ─── Feedback Buttons ────────────────────────────────────────────────────────

function FeedbackButtons({
  messageId,
  currentFeedback,
  onFeedback,
}: {
  messageId: string;
  currentFeedback: "up" | "down" | null | undefined;
  onFeedback?: (messageId: string, rating: "up" | "down") => void;
}) {
  const [hoveredBtn, setHoveredBtn] = useState<"up" | "down" | null>(null);

  if (!onFeedback) return null;

  const btnBase = `
    flex items-center justify-center w-7 h-7
    rounded-full
    text-[14px]
    transition-all duration-150
    cursor-pointer
  `;

  return (
    <div className="flex items-center gap-1 mt-2 opacity-0 group-hover/bubble:opacity-100 transition-opacity duration-200">
      {/* Thumbs Up */}
      <button
        onClick={() => onFeedback(messageId, "up")}
        onMouseEnter={() => setHoveredBtn("up")}
        onMouseLeave={() => setHoveredBtn(null)}
        className={`${btnBase} ${
          currentFeedback === "up"
            ? "bg-[var(--color-success-dim)] text-[var(--color-success)]"
            : hoveredBtn === "up"
            ? "bg-[rgba(239,243,244,0.08)] text-[var(--color-text-muted)]"
            : "text-[var(--color-text-dim)]"
        }`}
        aria-label="Good response"
      >
        👍
      </button>

      {/* Thumbs Down */}
      <button
        onClick={() => onFeedback(messageId, "down")}
        onMouseEnter={() => setHoveredBtn("down")}
        onMouseLeave={() => setHoveredBtn(null)}
        className={`${btnBase} ${
          currentFeedback === "down"
            ? "bg-[var(--color-danger-dim)] text-[var(--color-danger)]"
            : hoveredBtn === "down"
            ? "bg-[rgba(239,243,244,0.08)] text-[var(--color-text-muted)]"
            : "text-[var(--color-text-dim)]"
        }`}
        aria-label="Bad response"
      >
        👎
      </button>
    </div>
  );
}

// ─── User Bubble ─────────────────────────────────────────────────────────────

function UserBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end animate-[fade-up_0.3s_ease-out_both]">
      <div className="max-w-[75%] md:max-w-[60%]">
        {/* Image preview */}
        {message.image_data && (
          <div className="mb-2 flex justify-end">
            <img
              src={`data:${message.image_mimetype ?? "image/png"};base64,${message.image_data}`}
              alt="Attached image"
              className="max-w-[200px] max-h-[200px] rounded-[var(--radius-lg)] border border-[var(--color-border)] object-cover"
            />
          </div>
        )}

        {/* Message bubble */}
        <div
          className="
            bg-[var(--color-panel)]
            rounded-[20px] rounded-br-[4px]
            px-4 py-2.5
            text-[var(--text-base)] text-[var(--color-text-main)]
            leading-[1.5]
          "
        >
          {message.content}
        </div>

        {/* Timestamp */}
        <p className="text-[11px] text-[var(--color-text-dim)] mt-1 text-right pr-1">
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

// ─── AI Bubble ───────────────────────────────────────────────────────────────

function AIBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage;
  onFeedback?: (messageId: string, rating: "up" | "down") => void;
}) {
  return (
    <div className="flex justify-start animate-[fade-up_0.3s_ease-out_both] group/bubble">
      <div className="max-w-[85%] md:max-w-[75%]">
        {/* Avatar + name */}
        <div className="flex items-center gap-2 mb-1.5">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, rgba(29,155,240,0.2) 0%, rgba(239,243,244,0.08) 100%)',
              border: '1px solid rgba(29,155,240,0.15)',
            }}
          >
            ✦
          </div>
          <span className="text-[13px] font-medium text-[var(--color-text-muted)]">
            EduVerse
          </span>

          {/* Retrieval confidence badge */}
          {message.retrieval_label && (
            <span
              className={`
                text-[10px] font-medium px-1.5 py-0.5 rounded-full uppercase tracking-wider
                ${
                  message.retrieval_label === "CLASSROOM_GROUNDED"
                    ? "bg-[var(--color-success-dim)] text-[var(--color-success)]"
                    : message.retrieval_label === "CLASSROOM_LOW_CONFIDENCE"
                    ? "bg-[var(--color-warning-dim)] text-[var(--color-warning)]"
                    : "bg-[var(--color-danger-dim)] text-[var(--color-danger)]"
                }
              `}
            >
              {message.retrieval_label.replace("CLASSROOM_", "").replace(/_/g, " ")}
            </span>
          )}
        </div>

        {/* Content */}
        <div className="prose-eduverse">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
          >
            {message.content}
          </ReactMarkdown>

          {/* Streaming cursor */}
          {message.is_streaming && <StreamingCursor />}
        </div>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <CitationShelf citations={message.citations} />
        )}

        {/* Metadata row */}
        {message.retrieval_ms != null && !message.is_streaming && (
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[11px] text-[var(--color-text-dim)]">
              {(message.retrieval_ms / 1000).toFixed(1)}s
            </span>
            {message.trace_url && (
              <a
                href={message.trace_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] transition-colors underline underline-offset-2"
              >
                View trace
              </a>
            )}
          </div>
        )}

        {/* Feedback */}
        {!message.is_streaming && (
          <FeedbackButtons
            messageId={message.id}
            currentFeedback={message.feedback}
            onFeedback={onFeedback}
          />
        )}
      </div>
    </div>
  );
}

// ─── Exported Component ──────────────────────────────────────────────────────

export const MessageBubble = memo(function MessageBubble({
  message,
  onFeedback,
}: MessageBubbleProps) {
  if (message.role === "user") {
    return <UserBubble message={message} />;
  }
  return <AIBubble message={message} onFeedback={onFeedback} />;
});

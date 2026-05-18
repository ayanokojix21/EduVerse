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

import { memo, useState, useEffect, useRef } from "react";
<<<<<<< HEAD
=======
import { ContentRenderer } from "./ContentRenderer";

>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)
import type { ChatMessage, Citation } from "@/lib/types";
import { ContentRenderer } from "./ContentRenderer";
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

// ─── Agent Thought Process ───────────────────────────────────────────────────

function AgentThoughtProcess({
  thoughts,
  activeNodes,
  isStreaming,
}: {
  thoughts?: import("@/lib/types").AgentThought[];
  activeNodes?: string[];
  isStreaming?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(isStreaming ?? false);
  const prevThoughtCount = useRef(thoughts?.length ?? 0);
  const hasContent = (thoughts && thoughts.length > 0) || (activeNodes && activeNodes.length > 0);

  // Auto-open when streaming starts or when new thoughts arrive
  useEffect(() => {
    const currentCount = thoughts?.length ?? 0;
    if (isStreaming && currentCount > prevThoughtCount.current) {
      setIsOpen(true);
    }
    prevThoughtCount.current = currentCount;
  }, [isStreaming, thoughts?.length]);

  if (!hasContent) return null;

  return (
    <div className="mb-4" style={{ fontFamily: "inherit" }}>
      {/* ── Toggle Button ─────────────────────────────────────────── */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="
          flex items-center gap-2
          px-0 py-1
          text-[13px] font-medium
          cursor-pointer
          border-none bg-transparent
          transition-colors duration-150
        "
        style={{
          color: "var(--color-text-muted)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--color-text-main)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--color-text-muted)";
        }}
        aria-expanded={isOpen}
        aria-label={isOpen ? "Hide thinking" : "Show thinking"}
      >
        {/* Sparkle icon */}
        <span
          className="flex items-center justify-center w-5 h-5 text-[12px]"
          style={{
            background: "linear-gradient(135deg, rgba(29,155,240,0.3) 0%, rgba(147,130,255,0.3) 100%)",
            borderRadius: "6px",
            lineHeight: 1,
          }}
        >
          ✦
        </span>

        <span>{isOpen ? "Hide thinking" : "Show thinking"}</span>

        {/* Chevron */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transition: "transform 0.2s ease",
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>

        {/* Streaming indicator */}
        {isStreaming && (
          <span
            className="w-1.5 h-1.5 rounded-full ml-1"
            style={{
              backgroundColor: "var(--color-accent, #1d9bf0)",
              animation: "pulse-fast 0.8s ease-in-out infinite",
            }}
          />
        )}
      </button>

      {/* ── Collapsible Content ────────────────────────────────────── */}
      <div
        style={{
          maxHeight: isOpen ? "2000px" : "0px",
          opacity: isOpen ? 1 : 0,
          overflow: "hidden",
          transition: "max-height 0.35s ease, opacity 0.25s ease",
        }}
      >
        <div
          className="mt-2 pl-3"
          style={{
            borderLeft: "2px solid rgba(147,130,255,0.25)",
          }}
        >
          {/* Thought entries */}
          {thoughts?.map((t, i) => (
            <div
              key={i}
              className="mb-3"
              style={{
                animation: `fade-up 0.3s ease-out ${i * 0.05}s both`,
              }}
            >
              {/* Bold summary header */}
              <p
                className="text-[13px] font-semibold mb-0.5"
                style={{ color: "var(--color-text-main)" }}
              >
                {t.summary || t.node.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </p>

              {/* Italic reasoning body */}
              {t.reasoning && (
                <p
                  className="text-[13px] leading-relaxed"
                  style={{
                    color: "var(--color-text-dim)",
                    fontStyle: "italic",
                  }}
                >
                  {t.reasoning}
                </p>
              )}
            </div>
          ))}

          {/* Active node indicator (pulsing) */}
          {activeNodes && activeNodes.length > 0 && (
            <div
              className="flex items-center gap-2 mt-1 mb-2"
              style={{
                animation: "fade-up 0.3s ease-out both",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{
                  backgroundColor: "var(--color-accent, #1d9bf0)",
                  animation: "pulse-fast 0.8s ease-in-out infinite",
                }}
              />
              <span
                className="text-[13px]"
                style={{
                  color: "var(--color-text-dim)",
                  fontStyle: "italic",
                }}
              >
                {activeNodes
                  .map((n) => n.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))
                  .join(", ")}
                …
              </span>
            </div>
          )}
        </div>
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
  let displayContent: string = message.content;
  
  // Convert <think> tags to an HTML details accordion
  displayContent = displayContent.replace(
    /<think>/g, 
    '<details className="mb-4 text-[13px] text-[var(--color-text-dim)] border-l-2 border-[var(--color-border)] pl-3" open><summary className="cursor-pointer mb-2 font-medium">Model Reasoning</summary>\n\n'
  );
  displayContent = displayContent.replace(
    /<\/think>/g, 
    '\n\n</details>\n\n'
  );

  // Strip SSML [pause] artifacts often emitted by Gemini
  displayContent = displayContent.replace(/\[pause\]/gi, '');

  // Convert [Source 1, 2] or [Source 1] into Markdown links: [1](citation:1) [2](citation:2)
  displayContent = displayContent.replace(/\[Source\s+([0-9,\s]+)\]/gi, (match, nums) => {
    const ids = nums.split(',').map((n: string) => n.trim());
    return ids.map((id: string) => `[${id}](citation:${id})`).join(' ');
  });

  return (
    <div className="flex justify-start animate-[fade-up_0.3s_ease-out_both] group/bubble">
      <div className="max-w-[85%] md:max-w-[75%] min-w-[50%]">
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

        {/* Thought Process */}
        <AgentThoughtProcess 
          thoughts={message.agent_thoughts} 
          activeNodes={message.active_nodes} 
          isStreaming={message.is_streaming} 
        />

        {/* Content */}
        <div className="prose-eduverse">
<<<<<<< HEAD
          <ContentRenderer content={displayContent} isStreaming={message.is_streaming} />
=======
          <ContentRenderer 
            content={displayContent} 
            isStreaming={message.is_streaming} 
            citations={message.citations}
          />
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)

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

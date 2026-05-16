"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Chat Page — /chat/[courseId]
//
// 3-panel layout wired to the useChatStream state machine:
//   Left:   SessionSidebar (collapsible on mobile)
//   Center: ChatStream + HITLInterrupt + ChatInput
//   Right:  ObservabilityDrawer (toggle button)
//
// All chat state flows through the useChatStream hook.
// ─────────────────────────────────────────────────────────────────────────────

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { useChatStream } from "@/hooks/useChatStream";
import {
  ChatStream,
  ChatInput,
  HITLInterrupt,
  SessionSidebar,
  ObservabilityDrawer,
} from "@/components/chat";

export default function ChatPage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;

  // ── Chat state machine ──────────────────────────────────────────────────

  const chat = useChatStream(courseId);

  // ── UI state ────────────────────────────────────────────────────────────

  const [showSidebar, setShowSidebar] = useState(true);
  const [showDrawer, setShowDrawer] = useState(false);

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleSubmit = useCallback(
    (text: string, imageData?: string, imageMimetype?: string) => {
      chat.sendMessage(text, imageData, imageMimetype);
    },
    [chat.sendMessage]
  );

  const handleFeedback = useCallback(
    (messageId: string, rating: "up" | "down") => {
      chat.submitFeedback(messageId, rating);
    },
    [chat.submitFeedback]
  );

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      chat.loadSession(sessionId);
      // Close sidebar on mobile after selecting
      if (window.innerWidth < 768) setShowSidebar(false);
    },
    [chat.loadSession]
  );

  const handleNewChat = useCallback(() => {
    chat.reset();
    if (window.innerWidth < 768) setShowSidebar(false);
  }, [chat.reset]);

  const handleHITLDecision = useCallback(
    (decision: "search_web" | "socratic_only") => {
      chat.resumeHITL(decision);
    },
    [chat.resumeHITL]
  );

  const isInputDisabled =
    chat.status === "connecting" ||
    chat.status === "streaming" ||
    chat.status === "hitl_paused";

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex h-[calc(100dvh)] overflow-hidden">
      {/* ── Left: Session Sidebar ────────────────────────────────────────── */}
      {showSidebar && (
        <aside
          className="
            w-[260px] flex-shrink-0
            border-r border-[var(--color-border)]
            bg-[var(--color-bg)]
            hidden md:flex flex-col
            overflow-hidden
          "
        >
          <SessionSidebar
            courseId={courseId}
            activeSessionId={chat.sessionId}
            onSelectSession={handleSelectSession}
            onNewChat={handleNewChat}
          />
        </aside>
      )}

      {/* ── Center: Chat Area ────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-border)] flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* Sidebar toggle (mobile) */}
            <button
              onClick={() => setShowSidebar((p) => !p)}
              className="
                md:hidden
                w-8 h-8 rounded-full
                flex items-center justify-center
                text-[var(--color-text-dim)]
                hover:bg-[rgba(239,243,244,0.08)]
                transition-colors duration-150
              "
              aria-label="Toggle sessions"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </button>

            <h2 className="text-[15px] font-semibold text-[var(--color-text-main)] truncate">
              Chat
            </h2>

            {/* Session status */}
            {chat.sessionId && (
              <span className="text-[11px] text-[var(--color-text-dim)] hidden sm:inline">
                Session active
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Error indicator */}
            {chat.status === "error" && (
              <span className="text-[11px] text-[var(--color-danger)] mr-2">
                {chat.errorMessage ?? "Error occurred"}
              </span>
            )}

            {/* Observability toggle */}
            <button
              onClick={() => setShowDrawer((p) => !p)}
              className={`
                w-8 h-8 rounded-full
                flex items-center justify-center
                transition-colors duration-150
                ${
                  showDrawer
                    ? "bg-[rgba(239,243,244,0.1)] text-[var(--color-text-main)]"
                    : "text-[var(--color-text-dim)] hover:bg-[rgba(239,243,244,0.06)]"
                }
              `}
              aria-label="Toggle observability panel"
              title="Observability"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4" />
                <path d="M12 8h.01" />
              </svg>
            </button>

            {/* New chat button */}
            <button
              onClick={handleNewChat}
              className="
                w-8 h-8 rounded-full
                flex items-center justify-center
                text-[var(--color-text-dim)]
                hover:bg-[rgba(239,243,244,0.06)]
                transition-colors duration-150
              "
              aria-label="New chat"
              title="New chat"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>
        </header>

        {/* Chat stream */}
        <ChatStream
          messages={chat.messages}
          status={chat.status}
          statusMessage={chat.statusMessage}
          streamingText={chat.streamingText}
          agentThoughts={chat.agentThoughts}
          activeNodes={chat.activeNodes}
          onFeedback={handleFeedback}
        />

        {/* HITL Interrupt */}
        {chat.status === "hitl_paused" && (
          <div className="px-4 py-3 border-t border-[var(--color-border)]">
            <HITLInterrupt onDecision={handleHITLDecision} />
          </div>
        )}

        {/* Chat input */}
        <ChatInput
          onSubmit={handleSubmit}
          disabled={isInputDisabled}
          placeholder={
            chat.status === "hitl_paused"
              ? "Make a decision above to continue…"
              : "Ask about your course…"
          }
        />
      </div>

      {/* ── Right: Observability Drawer ──────────────────────────────────── */}
      {showDrawer && (
        <aside className="w-[340px] flex-shrink-0 hidden lg:flex flex-col overflow-hidden">
          <ObservabilityDrawer
            isOpen={showDrawer}
            onClose={() => setShowDrawer(false)}
            agentThoughts={chat.agentThoughts}
            retrievalLabel={chat.retrievalLabel}
            retrievalMs={chat.retrievalMs}
            mermaidGraph={chat.mermaidGraph}
            traceUrl={chat.traceUrl}
            critic={chat.critic}
            activeNodes={chat.activeNodes}
          />
        </aside>
      )}

      {/* ── Mobile sidebar overlay ───────────────────────────────────────── */}
      {showSidebar && (
        <>
          {/* Backdrop (mobile only) */}
          <div
            className="fixed inset-0 bg-black/60 z-40 md:hidden"
            onClick={() => setShowSidebar(false)}
          />
          <aside
            className="
              fixed left-0 top-0 bottom-0
              w-[280px] z-50
              bg-[var(--color-bg)]
              border-r border-[var(--color-border)]
              md:hidden
              animate-[slide-in-left_0.2s_ease-out]
              flex flex-col
            "
          >
            <SessionSidebar
              courseId={courseId}
              activeSessionId={chat.sessionId}
              onSelectSession={handleSelectSession}
              onNewChat={handleNewChat}
            />
          </aside>
        </>
      )}
    </div>
  );
}

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// SessionSidebar — Chat session list panel.
//
// Features:
// - Fetches and displays previous sessions for a course
// - "+ New Chat" button
// - Active session highlighting
// - Right-click context menu for rename and delete
// - Inline rename editing
// ─────────────────────────────────────────────────────────────────────────────

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { sessionsApi } from "@/lib/api";
import type { ChatSession } from "@/lib/types";

// ─── Props ───────────────────────────────────────────────────────────────────

interface SessionSidebarProps {
  courseId: string;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
}

// ─── Context Menu ────────────────────────────────────────────────────────────

interface ContextMenuState {
  sessionId: string;
  x: number;
  y: number;
}

function ContextMenu({
  state,
  onRename,
  onDelete,
  onClose,
}: {
  state: ContextMenuState;
  onRename: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div
      ref={ref}
      style={{ top: state.y, left: state.x }}
      className="
        fixed z-50
        bg-[var(--color-panel)] border border-[var(--color-border)]
        rounded-[var(--radius-lg)]
        shadow-[0_4px_24px_rgba(0,0,0,0.5)]
        py-1 min-w-[140px]
        animate-[fade-in_0.1s_ease-out]
      "
    >
      <button
        onClick={onRename}
        className="
          w-full text-left px-3 py-2
          text-[13px] text-[var(--color-text-main)]
          hover:bg-[rgba(239,243,244,0.06)]
          transition-colors duration-100
          flex items-center gap-2
        "
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
        </svg>
        Rename
      </button>
      <button
        onClick={onDelete}
        className="
          w-full text-left px-3 py-2
          text-[13px] text-[var(--color-danger)]
          hover:bg-[var(--color-danger-dim)]
          transition-colors duration-100
          flex items-center gap-2
        "
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 6h18" />
          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
        </svg>
        Delete
      </button>
    </div>
  );
}

// ─── Session Item ────────────────────────────────────────────────────────────

function SessionItem({
  session,
  isActive,
  onSelect,
  onContextMenu,
  isRenaming,
  onRenameSubmit,
  onRenameCancel,
}: {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  isRenaming: boolean;
  onRenameSubmit: (newTitle: string) => void;
  onRenameCancel: () => void;
}) {
  const [renameValue, setRenameValue] = useState(session.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming) {
      setRenameValue(session.title);
      setTimeout(() => inputRef.current?.select(), 0);
    }
  }, [isRenaming, session.title]);

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const trimmed = renameValue.trim();
      if (trimmed && trimmed !== session.title) {
        onRenameSubmit(trimmed);
      } else {
        onRenameCancel();
      }
    }
    if (e.key === "Escape") onRenameCancel();
  };

  const timeAgo = formatTimeAgo(session.updated_at ?? session.created_at);

  return (
    <button
      onClick={onSelect}
      onContextMenu={onContextMenu}
      className={`
        w-full text-left px-3 py-2.5
        rounded-[var(--radius-lg)]
        transition-all duration-150
        group/session
        ${
          isActive
            ? "bg-[rgba(239,243,244,0.08)]"
            : "hover:bg-[rgba(239,243,244,0.04)]"
        }
      `}
    >
      {isRenaming ? (
        <input
          ref={inputRef}
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={handleRenameKeyDown}
          onBlur={onRenameCancel}
          className="
            w-full bg-transparent
            text-[13px] text-[var(--color-text-main)]
            border-b border-[var(--color-border-focus)]
            outline-none pb-0.5
          "
          maxLength={100}
        />
      ) : (
        <>
          <p
            className={`
              text-[13px] font-medium truncate
              ${isActive ? "text-[var(--color-text-main)]" : "text-[var(--color-text-muted)]"}
            `}
          >
            {session.title}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px] text-[var(--color-text-dim)]">
              {timeAgo}
            </span>
            {session.message_count != null && (
              <span className="text-[11px] text-[var(--color-text-dim)]">
                · {session.message_count} msgs
              </span>
            )}
          </div>
        </>
      )}
    </button>
  );
}

// ─── Time Formatter ──────────────────────────────────────────────────────────

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function SessionSidebar({
  courseId,
  activeSessionId,
  onSelectSession,
  onNewChat,
}: SessionSidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);

  // ── Fetch sessions ──────────────────────────────────────────────────────

  const fetchSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await sessionsApi.list(courseId);
      setSessions(data);
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // ── Context menu handlers ───────────────────────────────────────────────

  const handleContextMenu = useCallback(
    (sessionId: string, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setContextMenu({ sessionId, x: e.clientX, y: e.clientY });
    },
    []
  );

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  // ── Rename ──────────────────────────────────────────────────────────────

  const startRename = useCallback(() => {
    if (!contextMenu) return;
    setRenamingId(contextMenu.sessionId);
    closeContextMenu();
  }, [contextMenu, closeContextMenu]);

  const handleRenameSubmit = useCallback(
    async (sessionId: string, newTitle: string) => {
      setRenamingId(null);
      try {
        await sessionsApi.rename(sessionId, newTitle);
        setSessions((prev) =>
          prev.map((s) => (s.session_id === sessionId ? { ...s, title: newTitle } : s))
        );
      } catch (err) {
        console.error("Failed to rename session:", err);
      }
    },
    []
  );

  // ── Delete ──────────────────────────────────────────────────────────────

  const handleDelete = useCallback(async () => {
    if (!contextMenu) return;
    const sessionId = contextMenu.sessionId;
    closeContextMenu();

    try {
      await sessionsApi.delete(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      // If we deleted the active session, start a new chat
      if (sessionId === activeSessionId) {
        onNewChat();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  }, [contextMenu, closeContextMenu, activeSessionId, onNewChat]);

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <h3 className="text-[14px] font-semibold text-[var(--color-text-main)]">
          Chats
        </h3>
        <button
          onClick={onNewChat}
          className="
            flex items-center gap-1.5
            px-3 py-1.5
            rounded-full
            text-[12px] font-medium
            text-[var(--color-text-main)]
            border border-[var(--color-border)]
            hover:bg-[rgba(239,243,244,0.06)]
            transition-colors duration-150
          "
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {isLoading ? (
          <div className="flex flex-col gap-2 px-2">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-[52px] rounded-[var(--radius-lg)] bg-[rgba(239,243,244,0.04)] animate-pulse"
              />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <p className="text-[13px] text-[var(--color-text-dim)]">
              No conversations yet
            </p>
            <p className="text-[12px] text-[var(--color-text-dim)] mt-1">
              Start chatting to create your first session
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => (
              <SessionItem
                key={session.session_id}
                session={session}
                isActive={session.session_id === activeSessionId}
                onSelect={() => onSelectSession(session.session_id)}
                onContextMenu={(e) => handleContextMenu(session.session_id, e)}
                isRenaming={renamingId === session.session_id}
                onRenameSubmit={(title) => handleRenameSubmit(session.session_id, title)}
                onRenameCancel={() => setRenamingId(null)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <ContextMenu
          state={contextMenu}
          onRename={startRename}
          onDelete={handleDelete}
          onClose={closeContextMenu}
        />
      )}
    </div>
  );
}

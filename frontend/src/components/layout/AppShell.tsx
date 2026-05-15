"use client";

// ─────────────────────────────────────────────────────────────────────────────
// AppShell — 3-column layout: Sidebar | Main Content | Optional Right Panel
// Used by the authenticated (app) route group.
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: React.ReactNode;
  /** Optional right panel (e.g. ObservabilityDrawer inline on wide screens) */
  rightPanel?: React.ReactNode;
  /** Whether to show the right panel */
  showRightPanel?: boolean;
}

export function AppShell({ children, rightPanel, showRightPanel = false }: AppShellProps) {
  return (
    <div className="flex w-full min-h-dvh bg-[var(--color-bg)]">
      {/* Left: Sidebar */}
      <Sidebar />

      {/* Center: Main content */}
      <main
        className={[
          "flex-1 min-w-0",
          showRightPanel && rightPanel ? "border-r border-[var(--color-border)]" : "",
          "overflow-y-auto",
        ].join(" ")}
        id="main-content"
      >
        {children}
      </main>

      {/* Right: Optional panel (inline on very wide screens) */}
      {showRightPanel && rightPanel && (
        <aside
          className={[
            "hidden 2xl:flex flex-col",
            "w-[340px] flex-shrink-0",
            "border-l border-[var(--color-border)]",
            "bg-[var(--color-sidebar)]",
            "overflow-y-auto",
          ].join(" ")}
          aria-label="Details panel"
        >
          {rightPanel}
        </aside>
      )}
    </div>
  );
}

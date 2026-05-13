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
    <div className="flex min-h-dvh bg-black">
      {/* Left: Sidebar */}
      <Sidebar />

      {/* Center: Main content */}
      <main
        className={[
          "flex-1 min-w-0",
          "border-r border-[#2F3336]",
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
            "border-l border-[#2F3336]",
            "bg-black",
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

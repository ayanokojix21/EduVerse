"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Drawer — Slide-in right panel (for CourseDrawer, ObservabilityDrawer)
// ─────────────────────────────────────────────────────────────────────────────

import React, { useEffect } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  width?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function Drawer({ open, onClose, title, width = "420px", children, footer }: DrawerProps) {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={[
          "fixed inset-0 z-40 bg-black/50 backdrop-blur-sm",
          "transition-opacity duration-300",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        ].join(" ")}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title ?? "Panel"}
        className={[
          "fixed top-0 right-0 bottom-0 z-50",
          "flex flex-col",
          "bg-[#16181C]",
          "border-l border-[#2F3336]",
          "shadow-[-24px_0_48px_rgba(0,0,0,0.4)]",
          "transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
        style={{ width }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2F3336] flex-shrink-0">
          <h2 className="text-[15px] font-semibold text-[#E7E9EA]">{title ?? ""}</h2>
          <button
            onClick={onClose}
            className={[
              "p-1.5 rounded-full",
              "text-[#71767B] hover:text-[#E7E9EA]",
              "hover:bg-[rgba(239,243,244,0.1)]",
              "transition-colors duration-150",
            ].join(" ")}
            aria-label="Close drawer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex-shrink-0 border-t border-[#2F3336] p-4">
            {footer}
          </div>
        )}
      </div>
    </>
  );
}

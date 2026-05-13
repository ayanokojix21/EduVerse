"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Modal — Animated dialog with backdrop blur and focus trap
// ─────────────────────────────────────────────────────────────────────────────

import React, { useCallback, useEffect, useRef } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg";
  /** If true, clicking backdrop does NOT close */
  persistent?: boolean;
  footer?: React.ReactNode;
}

const sizeMap = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-xl",
};

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
  persistent = false,
  footer,
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !persistent) onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose, persistent]);

  // Lock body scroll when open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (!persistent && e.target === e.currentTarget) onClose();
    },
    [onClose, persistent]
  );

  if (!open) return null;

  return (
    <div
      className={[
        "fixed inset-0 z-50",
        "flex items-center justify-center p-4",
        "bg-black/60 backdrop-blur-sm",
        "animate-[fade-in_0.15s_ease-out]",
      ].join(" ")}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        className={[
          "relative w-full",
          sizeMap[size],
          "bg-[#16181C]",
          "border border-[#2F3336]",
          "rounded-2xl",
          "shadow-[0_0_0_1px_#2F3336,0_24px_48px_rgba(0,0,0,0.6)]",
          "animate-[fade-up_0.2s_ease-out]",
          "flex flex-col",
          "max-h-[90dvh]",
        ].join(" ")}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        {(title || !persistent) && (
          <div className="flex items-start justify-between p-5 pb-0 flex-shrink-0">
            <div className="flex flex-col gap-1">
              {title && (
                <h2 id="modal-title" className="text-[16px] font-semibold text-[#E7E9EA]">
                  {title}
                </h2>
              )}
              {description && (
                <p className="text-[13px] text-[#71767B]">{description}</p>
              )}
            </div>
            {!persistent && (
              <button
                onClick={onClose}
                className={[
                  "ml-4 p-1.5 rounded-full flex-shrink-0",
                  "text-[#71767B] hover:text-[#E7E9EA]",
                  "hover:bg-[rgba(239,243,244,0.1)]",
                  "transition-colors duration-150",
                  "-mt-1 -mr-1",
                ].join(" ")}
                aria-label="Close modal"
              >
                <X size={16} />
              </button>
            )}
          </div>
        )}

        {/* Body */}
        <div className="p-5 overflow-y-auto flex-1">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="p-5 pt-0 flex-shrink-0 border-t border-[#2F3336] mt-0 pt-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

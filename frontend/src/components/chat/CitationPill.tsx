"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CitationPill — Inline [N] reference pill with hover tooltip.
// Click opens the source PDF via the proxy endpoint, or Classroom link.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useRef, useEffect, useCallback } from "react";
import type { Citation } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

interface CitationPillProps {
  citation: Citation;
}

export function CitationPill({ citation }: CitationPillProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLButtonElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(null);
  const { token } = useAuth();

  const handleMouseEnter = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setShowTooltip(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    timeoutRef.current = setTimeout(() => setShowTooltip(false), 200);
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleClick = async () => {
    if (citation.file_url) {
      // 1. Open a new window immediately to avoid popup blockers
      const newWindow = window.open('', '_blank');
      if (newWindow) {
        newWindow.document.write('<div style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh;">Loading secure document...</div>');
      }
      
      try {
        const proxyUrl = `/api/v1/proxy/pdf?url=${encodeURIComponent(citation.file_url)}`;
        const res = await fetch(proxyUrl, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        if (!res.ok) throw new Error("Failed to load PDF");
        
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        
        if (newWindow) {
          newWindow.location.href = objectUrl;
        }
      } catch (err) {
        if (newWindow) {
          newWindow.document.write('<div style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; color: red;">Failed to load secure document.</div>');
        }
      }
    } else if (citation.alternate_link) {
      window.open(citation.alternate_link, "_blank", "noopener");
    }
  };

  return (
    <span className="relative inline-block">
      <button
        ref={pillRef}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className="
          inline-flex items-center justify-center
          min-w-[1.375rem] h-[1.125rem]
          px-[5px] mx-[1px]
          rounded-[3px]
          bg-[rgba(239,243,244,0.08)]
          text-[11px] font-medium leading-none
          text-[var(--color-text-muted)]
          hover:bg-[rgba(239,243,244,0.15)]
          hover:text-[var(--color-text-main)]
          transition-colors duration-150
          cursor-pointer
          align-[1px]
        "
        aria-label={`Citation ${citation.source_index}: ${citation.title}`}
      >
        {citation.source_index}
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div
          ref={tooltipRef}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className="
            absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2
            w-[280px] max-w-[90vw]
            bg-[var(--color-panel)] border border-[var(--color-border)]
            rounded-[var(--radius-lg)]
            shadow-[0_4px_24px_rgba(0,0,0,0.5)]
            p-3
            animate-[fade-in_0.15s_ease-out]
          "
          role="tooltip"
        >
          {/* Title */}
          <p className="text-[13px] font-semibold text-[var(--color-text-main)] mb-1.5 line-clamp-2">
            {citation.title}
          </p>

          {/* Snippet */}
          <p className="text-[12px] text-[var(--color-text-muted)] leading-[1.5] line-clamp-3">
            {citation.snippet}
          </p>

          {/* Meta row */}
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[var(--color-border)]">
            <span className="text-[11px] text-[var(--color-text-dim)]">
              {citation.content_type}
            </span>
            {citation.page_number != null && (
              <span className="text-[11px] text-[var(--color-text-dim)]">
                p.{citation.page_number}
              </span>
            )}
          </div>

          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-[var(--color-border)]" />
        </div>
      )}
    </span>
  );
}

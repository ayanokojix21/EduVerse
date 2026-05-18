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
        let objectUrl = URL.createObjectURL(blob);
        
        // Append page number if available (works in most native browser PDF viewers)
        if (citation.page_number) {
          objectUrl += `#page=${citation.page_number}`;
        }
        
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
    <sup className="relative inline-block align-super -top-[0.2em] mx-[1px]">
      <button
        ref={pillRef}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className="
          inline-flex items-center justify-center
          min-w-[1.25rem] h-[1.125rem]
          px-[4px]
          rounded-[4px]
          bg-[rgba(29,155,240,0.15)]
          text-[10px] font-bold leading-none
          text-[var(--color-accent)]
          hover:bg-[var(--color-accent)]
          hover:text-white
          transition-all duration-150
          cursor-pointer
        "
        aria-label={`Citation ${citation.source_index}: ${citation.title}`}
      >
        {citation.source_index}
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <span
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
            block
            text-left
          "
          role="tooltip"
        >
          {/* Title */}
          <span className="block text-[13px] font-semibold text-[var(--color-text-main)] mb-1.5 line-clamp-2">
            {citation.title}
          </span>

          {/* Snippet */}
          <span className="block text-[12px] text-[var(--color-text-muted)] leading-[1.5] line-clamp-3">
            {citation.snippet}
          </span>

          {/* Meta row */}
          <span className="flex items-center gap-2 mt-2 pt-2 border-t border-[var(--color-border)]">
            <span className="text-[11px] text-[var(--color-text-dim)]">
              {citation.content_type}
            </span>
            {citation.page_number != null && (
              <span className="text-[11px] text-[var(--color-text-dim)]">
                p.{citation.page_number}
              </span>
            )}
          </span>

          {/* Arrow */}
          <span className="block absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-[var(--color-border)]" />
        </span>
      )}
    </sup>
  );
}

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// HITLInterrupt — Human-in-the-Loop decision block.
//
// Appears when the agent pauses to ask the student whether to:
//   • Search the web for supplementary information
//   • Stay Socratic (answer using only classroom materials)
//
// Styled with a warning-yellow (#FFD400) left border to clearly signal
// a decision point in the conversation flow.
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";

interface HITLInterruptProps {
  onDecision: (decision: "search_web" | "socratic_only") => void;
  disabled?: boolean;
}

export function HITLInterrupt({ onDecision, disabled = false }: HITLInterruptProps) {
  const [selected, setSelected] = useState<"search_web" | "socratic_only" | null>(null);

  const handleChoice = (decision: "search_web" | "socratic_only") => {
    if (disabled || selected) return;
    setSelected(decision);
    onDecision(decision);
  };

  return (
    <div
      className="
        animate-[fade-up_0.4s_ease-out_both]
        max-w-[720px] mx-auto
      "
    >
      <div
        className="
          border-l-[3px] border-[var(--color-warning)]
          bg-[var(--color-warning-dim)]
          rounded-r-[var(--radius-lg)]
          px-5 py-4
        "
      >
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <div
            className="
              w-5 h-5 rounded-full
              bg-[var(--color-warning)]
              flex items-center justify-center
              text-[11px] text-black font-bold
            "
          >
            ?
          </div>
          <h4 className="text-[14px] font-semibold text-[var(--color-text-main)]">
            Your course materials might not fully cover this topic
          </h4>
        </div>

        {/* Description */}
        <p className="text-[13px] text-[var(--color-text-muted)] mb-4 leading-[1.6]">
          I can search the web for additional context, or continue using only your 
          classroom materials with a Socratic approach. What would you prefer?
        </p>

        {/* Buttons */}
        <div className="flex flex-wrap gap-3">
          {/* Search Web */}
          <button
            onClick={() => handleChoice("search_web")}
            disabled={disabled || !!selected}
            className={`
              flex items-center gap-2
              px-4 py-2.5
              rounded-full
              text-[13px] font-medium
              transition-all duration-200
              cursor-pointer
              ${
                selected === "search_web"
                  ? "bg-[var(--color-warning)] text-black"
                  : selected
                  ? "opacity-40 cursor-not-allowed border border-[var(--color-border)] text-[var(--color-text-dim)]"
                  : "border border-[var(--color-warning)] text-[var(--color-warning)] hover:bg-[var(--color-warning)] hover:text-black"
              }
              ${disabled ? "opacity-50 pointer-events-none" : ""}
            `}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            Search the Web
          </button>

          {/* Socratic Only */}
          <button
            onClick={() => handleChoice("socratic_only")}
            disabled={disabled || !!selected}
            className={`
              flex items-center gap-2
              px-4 py-2.5
              rounded-full
              text-[13px] font-medium
              transition-all duration-200
              cursor-pointer
              ${
                selected === "socratic_only"
                  ? "bg-[var(--color-primary)] text-[var(--color-bg)]"
                  : selected
                  ? "opacity-40 cursor-not-allowed border border-[var(--color-border)] text-[var(--color-text-dim)]"
                  : "border border-[var(--color-border)] text-[var(--color-text-main)] hover:bg-[rgba(239,243,244,0.08)]"
              }
              ${disabled ? "opacity-50 pointer-events-none" : ""}
            `}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
            Socratic Only
          </button>
        </div>

        {/* Confirmation */}
        {selected && (
          <p className="text-[12px] text-[var(--color-text-dim)] mt-3 animate-[fade-in_0.2s_ease-out]">
            {selected === "search_web"
              ? "Searching the web for supplementary information…"
              : "Continuing with classroom materials only…"}
          </p>
        )}
      </div>
    </div>
  );
}

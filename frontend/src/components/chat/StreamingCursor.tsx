"use client";

// ─────────────────────────────────────────────────────────────────────────────
// StreamingCursor — pulsing block cursor appended during token streaming.
// Uses the `.streaming-cursor` class defined in globals.css.
// ─────────────────────────────────────────────────────────────────────────────

export function StreamingCursor() {
  return (
    <span
      className="streaming-cursor"
      aria-label="AI is typing"
      role="status"
    />
  );
}

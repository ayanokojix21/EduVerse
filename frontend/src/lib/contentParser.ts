// ─────────────────────────────────────────────────────────────────────────────
// contentParser — Segments Gemini's mixed-content output into typed blocks.
//
// Handles:
//   - Markdown (with inline/block LaTeX)
//   - Streaming-safe partial content
//   (Graph support temporarily removed)
// ─────────────────────────────────────────────────────────────────────────────

// ─── Types ───────────────────────────────────────────────────────────────────

export type ContentBlock =
  | { type: "markdown"; content: string }
  | { type: "error"; raw: string; error: string };

// ─── Parser ──────────────────────────────────────────────────────────────────

/**
 * Parse Gemini response content into an ordered array of typed blocks.
 *
 * Currently, everything is treated as markdown, but the architecture
 * supports adding specialized block parsers later.
 */
export function parseContent(raw: string): ContentBlock[] {
  if (!raw || raw.trim() === "") return [];

  // For now, treat everything as markdown
  return [{ type: "markdown", content: raw }];
}

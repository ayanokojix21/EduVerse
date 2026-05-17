// ─────────────────────────────────────────────────────────────────────────────
// contentParser — Segments Gemini's mixed-content output into typed blocks.
//
// Handles:
//   - Markdown (with inline/block LaTeX via $ and $$)
//   - Mermaid diagram fenced code blocks (```mermaid)
//   - Chart.js JSON fenced code blocks (```chart)
//   - [pause]/[break]/[silence] marker cleanup
//   - Streaming-safe partial content
// ─────────────────────────────────────────────────────────────────────────────

// ─── Types ───────────────────────────────────────────────────────────────────

export type ContentBlock =
  | { type: "markdown"; content: string }
  | { type: "mermaid"; content: string }
  | { type: "chart"; content: string }
  | { type: "error"; raw: string; error: string };

// ─── Marker Cleanup ──────────────────────────────────────────────────────────

/**
 * Remove bracketed stage-direction markers like [pause], [break], [silence],
 * [beat], etc. Replace with a subtle horizontal rule or empty string.
 */
const STAGE_DIRECTION_RE = /\[(?:pause|break|silence|beat|wait|thinking|reflect|breathe)(?:\s*\.\.\.)?\]/gi;

function cleanMarkers(text: string): string {
  // Replace stage directions with a thin separator (or nothing if at start/end)
  return text.replace(STAGE_DIRECTION_RE, "\n\n---\n\n").replace(/(\n\s*---\s*\n){2,}/g, "\n\n---\n\n");
}

// ─── Fenced Block Extraction ─────────────────────────────────────────────────

/**
 * Regex to match ```mermaid or ```chart fenced code blocks.
 * Captures: [1] = language, [2] = content
 *
 * The regex is designed to be streaming-safe: it only matches complete
 * fenced blocks (opening AND closing ```). Partial blocks are treated as
 * regular markdown and will be re-parsed once the closing fence arrives.
 */
const FENCED_BLOCK_RE = /```(mermaid|chart)\s*\n([\s\S]*?)```/g;

// ─── Parser ──────────────────────────────────────────────────────────────────

/**
 * Parse Gemini response content into an ordered array of typed blocks.
 *
 * 1. Clean up stage-direction markers ([pause], etc.)
 * 2. Extract ```mermaid and ```chart fenced code blocks
 * 3. Everything else is treated as markdown (with LaTeX preserved for KaTeX)
 */
export function parseContent(raw: string): ContentBlock[] {
  if (!raw || raw.trim() === "") return [];

  const cleaned = cleanMarkers(raw);
  const blocks: ContentBlock[] = [];
  let lastIndex = 0;

  // Reset regex state
  FENCED_BLOCK_RE.lastIndex = 0;

  let match: RegExpExecArray | null;
  while ((match = FENCED_BLOCK_RE.exec(cleaned)) !== null) {
    // Add any markdown before this fenced block
    const before = cleaned.slice(lastIndex, match.index).trim();
    if (before) {
      blocks.push({ type: "markdown", content: before });
    }

    const lang = match[1] as "mermaid" | "chart";
    const content = match[2].trim();

    if (content) {
      blocks.push({ type: lang, content });
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining markdown after the last fenced block
  const remaining = cleaned.slice(lastIndex).trim();
  if (remaining) {
    blocks.push({ type: "markdown", content: remaining });
  }

  // If nothing was extracted (no fenced blocks, everything was whitespace after cleanup)
  if (blocks.length === 0 && cleaned.trim()) {
    blocks.push({ type: "markdown", content: cleaned.trim() });
  }

  return blocks;
}

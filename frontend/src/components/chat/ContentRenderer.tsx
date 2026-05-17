"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ContentRenderer — Orchestrates rendering of parsed Gemini content blocks.
//
// Pipeline:
//   1. parseContent(raw) → ContentBlock[]
//   2. Render each block with the appropriate component:
//      - "markdown" → <MathMarkdown />
//      - "mermaid"  → <MermaidBlock />
//      - "chart"    → <ChartBlock />
//      - "error"    → <pre> fallback with error message
//
// This replaces the direct <ReactMarkdown> call in MessageBubble.
// The parent's .prose-eduverse wrapper is preserved — zero visual change.
// ─────────────────────────────────────────────────────────────────────────────

import { memo, useMemo } from "react";
import { parseContent, type ContentBlock } from "@/lib/contentParser";
import { MathMarkdown } from "./MathMarkdown";
import { MermaidBlock } from "./MermaidBlock";
import { ChartBlock } from "./ChartBlock";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ContentRendererProps {
  content: string;
  isStreaming?: boolean;
}

// ─── Error Block Fallback ────────────────────────────────────────────────────

function ErrorBlock({ raw, error }: { raw: string; error: string }) {
  return (
    <div className="my-3">
      <div
        className="flex items-center gap-2 px-3 py-2 text-[12px] rounded-t-lg"
        style={{
          background: "rgba(255, 212, 0, 0.08)",
          color: "var(--color-warning)",
          borderBottom: "1px solid rgba(255, 212, 0, 0.15)",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        {error}
      </div>
      <pre
        className="p-3 text-[12px] overflow-x-auto rounded-b-lg"
        style={{
          background: "var(--color-panel)",
          color: "var(--color-text-muted)",
          margin: 0,
          border: "1px solid var(--color-border)",
          borderTop: "none",
        }}
      >
        <code>{raw}</code>
      </pre>
    </div>
  );
}

// ─── Block Renderer ──────────────────────────────────────────────────────────

function renderBlock(block: ContentBlock, index: number) {
  switch (block.type) {
    case "markdown":
      return <MathMarkdown key={`md-${index}`} content={block.content} />;

    case "mermaid":
      return <MermaidBlock key={`mermaid-${index}`} code={block.content} />;

    case "chart":
      return <ChartBlock key={`chart-${index}`} code={block.content} />;

    case "error":
      return (
        <ErrorBlock
          key={`err-${index}`}
          raw={block.raw}
          error={block.error}
        />
      );

    default:
      return null;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

export const ContentRenderer = memo(function ContentRenderer({
  content,
}: ContentRendererProps) {
  // During streaming, re-parse on every token. The parser is fast (<1ms).
  // After streaming completes, the parsed result is memoized.
  const blocks = useMemo(() => parseContent(content), [content]);

  if (!blocks.length) return null;

  // Single markdown block — render directly without wrapper
  if (blocks.length === 1 && blocks[0].type === "markdown") {
    return <MathMarkdown content={blocks[0].content} />;
  }

  return <>{blocks.map(renderBlock)}</>;
});

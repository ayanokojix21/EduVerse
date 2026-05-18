"use client";

// ─────────────────────────────────────────────────────────────────────────────
<<<<<<< HEAD
// MathMarkdown — Markdown renderer with KaTeX math and custom code blocks.
//
// Supports:
//   - GitHub Flavored Markdown (tables, strikethrough, etc.)
//   - Inline math: $...$  →  KaTeX inline
//   - Display math: $$...$$ → KaTeX block
//   - Mermaid fenced code blocks (delegated to MermaidBlock)
//   - Chart JSON fenced code blocks (delegated to ChartBlock)
//   - Raw HTML passthrough
=======
// MathMarkdown — Fallback markdown renderer.
// KaTeX and Plotly have been removed to prevent Next.js Turbopack OOM crashes.
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)
// ─────────────────────────────────────────────────────────────────────────────

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
<<<<<<< HEAD
import "katex/dist/katex.min.css";

import { MermaidBlock } from "./MermaidBlock";
import { ChartBlock } from "./ChartBlock";
=======

import type { Citation } from "@/lib/types";
import { CitationPill } from "./CitationPill";
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)

// ─── Props ───────────────────────────────────────────────────────────────────

interface MathMarkdownProps {
  content: string;
<<<<<<< HEAD
}

// ─── Custom Code Block Renderer ──────────────────────────────────────────────

/**
 * Custom renderer for fenced code blocks inside ReactMarkdown.
 * Intercepts `mermaid` and `chart` languages to render them as
 * interactive components instead of plain <code>.
 */
function CodeBlock({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) {
  // Extract language from className (e.g., "language-mermaid")
  const match = /language-(\w+)/.exec(className || "");
  const lang = match?.[1];
  const code = String(children).replace(/\n$/, "");

  if (lang === "mermaid") {
    return <MermaidBlock code={code} />;
  }

  if (lang === "chart") {
    return <ChartBlock code={code} />;
  }

  // Default code block rendering — inline vs block
  const isInline = !className;
  if (isInline) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
=======
  citations?: Citation[];
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)
}

// ─── Component ───────────────────────────────────────────────────────────────

export const MathMarkdown = memo(function MathMarkdown({
  content,
<<<<<<< HEAD
=======
  citations,
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)
}: MathMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, rehypeKatex]}
      components={{
<<<<<<< HEAD
        code: CodeBlock,
=======
        a: ({ node, ...props }) => {
          if (props.href?.startsWith("citation:")) {
            const id = parseInt(props.href.replace("citation:", ""), 10);
            const citation = citations?.find((c) => c.source_index === id);
            if (citation) {
              return <CitationPill citation={citation} />;
            }
            return <sup className="text-accent">[{id}]</sup>;
          }
          return (
            <a {...props} target="_blank" rel="noopener noreferrer">
              {props.children}
            </a>
          );
        },
>>>>>>> 36a4f06 (feat: integrate KaTeX math rendering, add content parser for citations, and secure PDF proxy document loading)
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

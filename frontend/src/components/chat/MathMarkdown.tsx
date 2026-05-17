"use client";

// ─────────────────────────────────────────────────────────────────────────────
// MathMarkdown — Markdown renderer with KaTeX math and custom code blocks.
//
// Supports:
//   - GitHub Flavored Markdown (tables, strikethrough, etc.)
//   - Inline math: $...$  →  KaTeX inline
//   - Display math: $$...$$ → KaTeX block
//   - Mermaid fenced code blocks (delegated to MermaidBlock)
//   - Chart JSON fenced code blocks (delegated to ChartBlock)
//   - Raw HTML passthrough
// ─────────────────────────────────────────────────────────────────────────────

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

import { MermaidBlock } from "./MermaidBlock";
import { ChartBlock } from "./ChartBlock";

// ─── Props ───────────────────────────────────────────────────────────────────

interface MathMarkdownProps {
  content: string;
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
}

// ─── Component ───────────────────────────────────────────────────────────────

export const MathMarkdown = memo(function MathMarkdown({
  content,
}: MathMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, rehypeKatex]}
      components={{
        code: CodeBlock,
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

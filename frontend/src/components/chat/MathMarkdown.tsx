"use client";

// ─────────────────────────────────────────────────────────────────────────────
// MathMarkdown — Fallback markdown renderer.
// KaTeX and Plotly have been removed to prevent Next.js Turbopack OOM crashes.
// ─────────────────────────────────────────────────────────────────────────────

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// ─── Props ───────────────────────────────────────────────────────────────────

interface MathMarkdownProps {
  content: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export const MathMarkdown = memo(function MathMarkdown({
  content,
}: MathMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
    >
      {content}
    </ReactMarkdown>
  );
});

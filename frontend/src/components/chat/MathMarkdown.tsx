"use client";

// ─────────────────────────────────────────────────────────────────────────────
// MathMarkdown — Fallback markdown renderer.
// KaTeX and Plotly have been removed to prevent Next.js Turbopack OOM crashes.
// ─────────────────────────────────────────────────────────────────────────────

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";

import type { Citation } from "@/lib/types";
import { CitationPill } from "./CitationPill";

// ─── Props ───────────────────────────────────────────────────────────────────

interface MathMarkdownProps {
  content: string;
  citations?: Citation[];
}

// ─── Component ───────────────────────────────────────────────────────────────

export const MathMarkdown = memo(function MathMarkdown({
  content,
  citations,
}: MathMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, rehypeKatex]}
      components={{
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
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

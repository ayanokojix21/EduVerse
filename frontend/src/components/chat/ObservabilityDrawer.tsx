"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ObservabilityDrawer — Right-side panel showing agent internals.
//
// Sections:
// 1. Retrieval Confidence — color-coded badge + score
// 2. Agent Thoughts — timeline of reasoning steps
// 3. Execution Graph — Mermaid diagram of the agent graph
// 4. Critic Review — quality assessment from the critic agent
// 5. LangSmith Trace — deep link to the full trace
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef } from "react";
import type { AgentThought } from "@/lib/types";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ObservabilityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  // Data from the chat state
  agentThoughts: AgentThought[];
  retrievalLabel: string | null;
  retrievalMs: number | null;
  mermaidGraph: string | null;
  traceUrl: string | null;
  critic: Record<string, unknown> | null;
  activeNodes: string[];
}

// ─── Retrieval Badge ─────────────────────────────────────────────────────────

function RetrievalBadge({
  label,
  retrievalMs,
}: {
  label: string | null;
  retrievalMs: number | null;
}) {
  if (!label) return null;

  const config = {
    CLASSROOM_GROUNDED: {
      color: "var(--color-success)",
      bg: "var(--color-success-dim)",
      text: "Grounded",
      description: "Answer is well-supported by your course materials.",
    },
    CLASSROOM_LOW_CONFIDENCE: {
      color: "var(--color-warning)",
      bg: "var(--color-warning-dim)",
      text: "Low Confidence",
      description: "Some relevant materials found, but confidence is limited.",
    },
    CLASSROOM_INSUFFICIENT: {
      color: "var(--color-danger)",
      bg: "var(--color-danger-dim)",
      text: "Insufficient",
      description: "Course materials don't adequately cover this topic.",
    },
  }[label] ?? {
    color: "var(--color-text-dim)",
    bg: "rgba(239,243,244,0.04)",
    text: label,
    description: "",
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
          Retrieval
        </h4>
        {retrievalMs != null && (
          <span className="text-[11px] text-[var(--color-text-dim)]">
            {(retrievalMs / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: config.color }}
        />
        <span
          className="text-[13px] font-medium px-2 py-0.5 rounded-full"
          style={{ color: config.color, backgroundColor: config.bg }}
        >
          {config.text}
        </span>
      </div>

      {config.description && (
        <p className="text-[12px] text-[var(--color-text-dim)] mt-2 leading-[1.5]">
          {config.description}
        </p>
      )}
    </div>
  );
}

// ─── Agent Thoughts Timeline ─────────────────────────────────────────────────

function ThoughtsTimeline({
  thoughts,
  activeNodes,
}: {
  thoughts: AgentThought[];
  activeNodes: string[];
}) {
  if (!thoughts.length && !activeNodes.length) return null;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Agent Thoughts
      </h4>

      <div className="space-y-0">
        {thoughts.map((thought, i) => (
          <div key={i} className="flex gap-3 group">
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-2 h-2 rounded-full mt-1.5 flex-shrink-0
                  ${
                    activeNodes.includes(thought.node)
                      ? "bg-[var(--color-warning)] animate-[pulse-fast_0.8s_ease-in-out_infinite]"
                      : "bg-[var(--color-border-focus)]"
                  }
                `}
              />
              {i < thoughts.length - 1 && (
                <div className="w-px flex-1 bg-[var(--color-border)] min-h-[16px]" />
              )}
            </div>

            {/* Content */}
            <div className="pb-3 flex-1 min-w-0">
              <p className="text-[12px] font-medium text-[var(--color-text-main)]">
                {thought.node}
              </p>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5 leading-[1.5] break-words">
                {thought.reasoning}
              </p>
            </div>
          </div>
        ))}

        {/* Active nodes indicator */}
        {activeNodes.length > 0 && (
          <div className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="w-2 h-2 rounded-full mt-1.5 bg-[var(--color-warning)] animate-[pulse-fast_0.8s_ease-in-out_infinite]" />
            </div>
            <div className="pb-1">
              <p className="text-[12px] text-[var(--color-text-muted)] italic">
                Running: {activeNodes.join(", ")}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Mermaid Graph ───────────────────────────────────────────────────────────

function MermaidGraph({ graph }: { graph: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    // Dynamically import mermaid to avoid SSR issues
    import("mermaid").then((mermaid) => {
      mermaid.default.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
          darkMode: true,
          background: "#16181C",
          primaryColor: "#2F3336",
          primaryTextColor: "#E7E9EA",
          primaryBorderColor: "#536471",
          lineColor: "#536471",
          secondaryColor: "#1E2024",
          tertiaryColor: "#0D0E10",
        },
      });

      const id = `mermaid-${Date.now()}`;
      mermaid.default
        .render(id, graph)
        .then(({ svg }) => {
          if (containerRef.current) {
            containerRef.current.innerHTML = svg;
          }
        })
        .catch((err) => {
          console.warn("Mermaid render failed:", err);
          if (containerRef.current) {
            containerRef.current.innerHTML = `<pre class="text-[11px] text-[var(--color-text-dim)] whitespace-pre-wrap">${graph}</pre>`;
          }
        });
    });
  }, [graph]);

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Execution Graph
      </h4>
      <div
        ref={containerRef}
        className="overflow-x-auto [&_svg]:max-w-full"
      />
    </div>
  );
}

// ─── Critic Review ───────────────────────────────────────────────────────────

function CriticReview({ critic }: { critic: Record<string, unknown> }) {
  const score = critic.score as number | undefined;
  const feedback = critic.feedback as string | undefined;
  const suggestions = critic.suggestions as string[] | undefined;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
          Critic Review
        </h4>
        {score != null && (
          <span
            className={`
              text-[12px] font-semibold px-2 py-0.5 rounded-full
              ${
                score >= 0.8
                  ? "bg-[var(--color-success-dim)] text-[var(--color-success)]"
                  : score >= 0.5
                  ? "bg-[var(--color-warning-dim)] text-[var(--color-warning)]"
                  : "bg-[var(--color-danger-dim)] text-[var(--color-danger)]"
              }
            `}
          >
            {(score * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {feedback && (
        <p className="text-[12px] text-[var(--color-text-muted)] leading-[1.6]">
          {feedback}
        </p>
      )}

      {suggestions && suggestions.length > 0 && (
        <ul className="mt-2 space-y-1">
          {suggestions.map((s, i) => (
            <li key={i} className="text-[11px] text-[var(--color-text-dim)] flex gap-1.5">
              <span className="text-[var(--color-text-dim)] flex-shrink-0">•</span>
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { Drawer } from "@/components/ui/Drawer";

// ─── Main Component ──────────────────────────────────────────────────────────

export function ObservabilityDrawer({
  isOpen,
  onClose,
  agentThoughts,
  retrievalLabel,
  retrievalMs,
  mermaidGraph,
  traceUrl,
  critic,
  activeNodes,
}: ObservabilityDrawerProps) {
  if (!isOpen) return null;

  const hasContent =
    retrievalLabel ||
    agentThoughts.length > 0 ||
    activeNodes.length > 0 ||
    mermaidGraph ||
    critic ||
    traceUrl;

  return (
    <Drawer
      open={isOpen}
      onClose={onClose}
      title="Observability"
      inline={true}
    >
      <div className="px-4 py-4 space-y-4">
        {!hasContent ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-[13px] text-[var(--color-text-dim)]">
              No observability data yet
            </p>
            <p className="text-[12px] text-[var(--color-text-dim)] mt-1">
              Send a message to see agent internals
            </p>
          </div>
        ) : (
          <>
            {/* Retrieval Badge */}
            <RetrievalBadge label={retrievalLabel} retrievalMs={retrievalMs} />

            {/* Agent Thoughts */}
            <ThoughtsTimeline thoughts={agentThoughts} activeNodes={activeNodes} />

            {/* Mermaid Graph */}
            {mermaidGraph && <MermaidGraph graph={mermaidGraph} />}

            {/* Critic Review */}
            {critic && Object.keys(critic).length > 0 && (
              <CriticReview critic={critic} />
            )}

            {/* Trace Link */}
            {traceUrl && (
              <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
                <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
                  Full Trace
                </h4>
                <a
                  href={traceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="
                    inline-flex items-center gap-1.5
                    text-[13px] text-[var(--color-text-main)]
                    hover:text-[var(--color-primary)]
                    underline underline-offset-2
                    transition-colors duration-150
                  "
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                  Open in LangSmith
                </a>
              </div>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
}

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ObservabilityDrawer — Right-side panel showing agent internals.
//
// Sections:
// 1. Retrieval Confidence — color-coded badge + score
// 2. Live Execution Graph — SVG pipeline with animated node/edge states
// 3. Critic Review — quality assessment (severity, issues, pedagogy)
// ─────────────────────────────────────────────────────────────────────────────

import { useMemo } from "react";
import type { AgentThought } from "@/lib/types";
import { Drawer } from "@/components/ui/Drawer";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ObservabilityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  agentThoughts: AgentThought[];
  retrievalLabel: string | null;
  retrievalMs: number | null;
  mermaidGraph: string | null;
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

// ─── Live Execution Graph ────────────────────────────────────────────────────

// The full pipeline node order
const PIPELINE_NODES = [
  "input_moderator",
  "integrity_guard",
  "orchestrator",
  "planner",
  "executor",
  "hitl",
  "distiller",
  "generator",
  "validator",
  "formatter",
  "critic_agent",
  "output_moderator",
];

const NODE_LABELS: Record<string, string> = {
  input_moderator: "Input Safety",
  integrity_guard: "Integrity Check",
  orchestrator: "Orchestrator",
  planner: "Query Planner",
  executor: "Retriever",
  hitl: "HITL Gate",
  distiller: "Distiller",
  generator: "Generator",
  validator: "Validator",
  formatter: "Formatter",
  critic_agent: "Critic",
  output_moderator: "Output Shield",
};

type NodeState = "pending" | "active" | "done";

interface LoopBackEdge {
  fromNode: string;
  toNode: string;
  fromPipeIdx: number;
  toPipeIdx: number;
  label: string;
}

function LiveExecutionGraph({
  agentThoughts,
  activeNodes,
}: {
  agentThoughts: AgentThought[];
  activeNodes: string[];
}) {
  // Build the ordered execution trace (only pipeline nodes)
  const executionTrace = useMemo(
    () => agentThoughts.map((t) => t.node).filter((n) => PIPELINE_NODES.includes(n)),
    [agentThoughts],
  );

  // Detect loop-back edges from the execution trace
  const loopBacks = useMemo(() => {
    const edges: LoopBackEdge[] = [];
    for (let i = 1; i < executionTrace.length; i++) {
      const prevIdx = PIPELINE_NODES.indexOf(executionTrace[i - 1]);
      const currIdx = PIPELINE_NODES.indexOf(executionTrace[i]);
      if (currIdx >= 0 && prevIdx >= 0 && currIdx <= prevIdx) {
        const sameCount = edges.filter(
          (e) => e.fromNode === executionTrace[i - 1] && e.toNode === executionTrace[i],
        ).length;
        edges.push({
          fromNode: executionTrace[i - 1],
          toNode: executionTrace[i],
          fromPipeIdx: prevIdx,
          toPipeIdx: currIdx,
          label: `Retry ${sameCount + 1}`,
        });
      }
    }
    return edges;
  }, [executionTrace]);

  // Count visits per node
  const visitCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of executionTrace) {
      counts[n] = (counts[n] || 0) + 1;
    }
    return counts;
  }, [executionTrace]);

  // Compute current-phase node states — resets downstream nodes on loop-back
  // When the trace shows e.g. [..., validator, generator], processing "generator"
  // clears generator and everything after it, so validator goes back to pending.
  const nodeStates = useMemo(() => {
    const currentPhaseCompleted = new Set<string>();
    for (const nodeName of executionTrace) {
      const nodeIdx = PIPELINE_NODES.indexOf(nodeName);
      if (nodeIdx < 0) continue;
      // Clear this node and everything downstream — they need to re-execute
      for (let j = nodeIdx; j < PIPELINE_NODES.length; j++) {
        currentPhaseCompleted.delete(PIPELINE_NODES[j]);
      }
      currentPhaseCompleted.add(nodeName);
    }

    const activeSet = new Set(activeNodes);
    const states: Record<string, NodeState> = {};
    for (const node of PIPELINE_NODES) {
      if (activeSet.has(node)) {
        states[node] = "active";
      } else if (currentPhaseCompleted.has(node)) {
        states[node] = "done";
      } else {
        states[node] = "pending";
      }
    }
    return states;
  }, [executionTrace, activeNodes]);

  // Find the furthest progressed node index for edge coloring
  const furthestIndex = useMemo(() => {
    let maxIdx = -1;
    for (let i = 0; i < PIPELINE_NODES.length; i++) {
      const state = nodeStates[PIPELINE_NODES[i]];
      if (state === "active" || state === "done") {
        maxIdx = i;
      }
    }
    return maxIdx;
  }, [nodeStates]);

  // Filter to only show nodes that are relevant
  const visibleNodes = useMemo(() => {
    if (furthestIndex < 0) return PIPELINE_NODES.slice(0, 3);
    const endIdx = Math.min(furthestIndex + 2, PIPELINE_NODES.length);
    return PIPELINE_NODES.slice(0, endIdx);
  }, [furthestIndex]);

  const nodeHeight = 36;
  const nodeWidth = 150;
  const gapY = 14;
  const paddingX = 20;
  const paddingY = 16;
  const hasLoopBacks = loopBacks.length > 0;
  const loopBackMargin = hasLoopBacks ? 55 : 0;
  const svgWidth = nodeWidth + paddingX * 2 + loopBackMargin;
  const svgHeight = visibleNodes.length * (nodeHeight + gapY) - gapY + paddingY * 2;

  const getNodeColor = (state: NodeState) => {
    switch (state) {
      case "active": return { fill: "rgba(29,155,240,0.15)", stroke: "#1d9bf0", text: "#e7e9ea" };
      case "done":   return { fill: "rgba(74,222,128,0.1)", stroke: "#4ade80", text: "#a1a1aa" };
      default:       return { fill: "rgba(239,243,244,0.03)", stroke: "#2f3336", text: "#536471" };
    }
  };

  const getEdgeColor = (fromIdx: number) => {
    if (fromIdx < furthestIndex) return "#4ade80";
    if (fromIdx === furthestIndex) return "#1d9bf0";
    return "#2f3336";
  };

  // Helper: get the Y-center of a node by its visible index
  const getNodeYCenter = (visibleIdx: number) =>
    paddingY + visibleIdx * (nodeHeight + gapY) + nodeHeight / 2;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Execution Graph
      </h4>

      <div className="flex justify-center overflow-visible">
        <svg
          width={svgWidth}
          height={svgHeight}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="block"
        >
          <defs>
            {/* Glow filter for active nodes */}
            <filter id="active-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feFlood floodColor="#1d9bf0" floodOpacity="0.3" />
              <feComposite in2="blur" operator="in" />
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Arrow markers */}
            <marker id="arrow-pending" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#2f3336" />
            </marker>
            <marker id="arrow-active" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#1d9bf0" />
            </marker>
            <marker id="arrow-done" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#4ade80" />
            </marker>
            {/* Loop-back arrow marker — amber */}
            <marker id="arrow-loopback" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#f59e0b" />
            </marker>
          </defs>

          {/* Forward edges */}
          {visibleNodes.map((node, i) => {
            if (i >= visibleNodes.length - 1) return null;
            const y1 = paddingY + i * (nodeHeight + gapY) + nodeHeight;
            const y2 = paddingY + (i + 1) * (nodeHeight + gapY);
            const cx = paddingX + nodeWidth / 2;
            const edgeColor = getEdgeColor(i);
            const markerRef =
              i < furthestIndex ? "url(#arrow-done)" :
              i === furthestIndex ? "url(#arrow-active)" :
              "url(#arrow-pending)";

            return (
              <g key={`edge-${i}`}>
                <line
                  x1={cx}
                  y1={y1}
                  x2={cx}
                  y2={y2}
                  stroke={edgeColor}
                  strokeWidth={i <= furthestIndex ? 2 : 1}
                  markerEnd={markerRef}
                  style={{
                    transition: "stroke 0.5s ease, stroke-width 0.3s ease",
                  }}
                />
                {/* Animated pulse on active edge */}
                {i === furthestIndex && (
                  <circle r="3" fill="#1d9bf0" opacity="0.8">
                    <animateMotion
                      dur="1.2s"
                      repeatCount="indefinite"
                      path={`M ${cx} ${y1} L ${cx} ${y2}`}
                    />
                  </circle>
                )}
              </g>
            );
          })}

          {/* Loop-back arrows — curved right-side paths */}
          {loopBacks.map((lb, lbIdx) => {
            const fromVisIdx = visibleNodes.indexOf(lb.fromNode);
            const toVisIdx = visibleNodes.indexOf(lb.toNode);
            if (fromVisIdx < 0 || toVisIdx < 0) return null;

            const fromY = getNodeYCenter(fromVisIdx);
            const toY = getNodeYCenter(toVisIdx);
            const rightX = paddingX + nodeWidth;
            const offset = 30 + lbIdx * 12; // stagger multiple loop-backs
            const r = 8; // corner radius

            // Path: right from source → up → left into target
            const path = [
              `M ${rightX} ${fromY}`,
              `L ${rightX + offset - r} ${fromY}`,
              `Q ${rightX + offset} ${fromY} ${rightX + offset} ${fromY - r}`,
              `L ${rightX + offset} ${toY + r}`,
              `Q ${rightX + offset} ${toY} ${rightX + offset - r} ${toY}`,
              `L ${rightX} ${toY}`,
            ].join(" ");

            const labelX = rightX + offset + 5;
            const labelY = (fromY + toY) / 2;

            return (
              <g key={`loopback-${lbIdx}`} style={{ animation: "fade-in 0.5s ease-out both" }}>
                {/* Loop-back path */}
                <path
                  d={path}
                  fill="none"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                  markerEnd="url(#arrow-loopback)"
                  style={{ transition: "opacity 0.4s ease" }}
                />
                {/* Animated pulse on loop-back */}
                <circle r="2.5" fill="#f59e0b" opacity="0.7">
                  <animateMotion dur="2s" repeatCount="indefinite" path={path} />
                </circle>
                {/* Label */}
                <text
                  x={labelX}
                  y={labelY}
                  fontSize="9"
                  fill="#f59e0b"
                  fontWeight={500}
                  textAnchor="start"
                  dominantBaseline="middle"
                  style={{ opacity: 0.85 }}
                >
                  {lb.label}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {visibleNodes.map((node, i) => {
            const x = paddingX;
            const y = paddingY + i * (nodeHeight + gapY);
            const state = nodeStates[node];
            const colors = getNodeColor(state);
            const label = NODE_LABELS[node] || node;
            const cornerRadius = 8;
            const visits = visitCounts[node] ?? 0;

            return (
              <g
                key={node}
                style={{
                  transition: "opacity 0.4s ease",
                  animation: state !== "pending" ? "fade-up 0.3s ease-out both" : undefined,
                }}
              >
                {/* Node background */}
                <rect
                  x={x}
                  y={y}
                  width={nodeWidth}
                  height={nodeHeight}
                  rx={cornerRadius}
                  ry={cornerRadius}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth={state === "active" ? 1.5 : 1}
                  filter={state === "active" ? "url(#active-glow)" : undefined}
                  style={{
                    transition: "fill 0.5s ease, stroke 0.5s ease, stroke-width 0.3s ease",
                  }}
                />

                {/* Status icon */}
                {state === "done" && (
                  <text
                    x={x + 12}
                    y={y + nodeHeight / 2 + 1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="11"
                    fill="#4ade80"
                  >
                    ✓
                  </text>
                )}
                {state === "active" && (
                  <circle
                    cx={x + 12}
                    cy={y + nodeHeight / 2}
                    r="3"
                    fill="#1d9bf0"
                  >
                    <animate
                      attributeName="opacity"
                      values="1;0.3;1"
                      dur="1s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}

                {/* Label */}
                <text
                  x={x + (state !== "pending" ? 24 : 12)}
                  y={y + nodeHeight / 2 + 1}
                  dominantBaseline="middle"
                  fontSize="11.5"
                  fontFamily="inherit"
                  fontWeight={state === "active" ? 600 : 400}
                  fill={colors.text}
                  style={{
                    transition: "fill 0.5s ease",
                  }}
                >
                  {label}
                </text>

                {/* Visit count badge — shown for nodes that ran more than once */}
                {visits > 1 && (
                  <g>
                    <circle
                      cx={x + nodeWidth - 14}
                      cy={y + nodeHeight / 2}
                      r="9"
                      fill="rgba(245, 158, 11, 0.12)"
                      stroke="#f59e0b"
                      strokeWidth="0.75"
                    />
                    <text
                      x={x + nodeWidth - 14}
                      y={y + nodeHeight / 2 + 0.5}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize="8.5"
                      fontWeight={600}
                      fill="#f59e0b"
                    >
                      ×{visits}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ─── Critic Review ───────────────────────────────────────────────────────────

function CriticReview({ critic }: { critic: Record<string, unknown> }) {
  // Map to actual CriticOutput schema from the backend
  const severity = critic.severity as string | undefined;
  const passed = critic.passed as boolean | undefined;
  const issues = critic.issues as string[] | undefined;
  const requiredFacts = critic.required_facts as string[] | undefined;
  const pedagogicalFidelity = critic.pedagogical_fidelity as string | undefined;
  const isSocratic = critic.is_socratic as boolean | undefined;
  const validatedCitations = critic.validated_citations as number | undefined;

  // Don't show empty/pending reviews
  if (severity === undefined && passed === undefined) return null;

  const severityConfig = {
    none: {
      color: "var(--color-success)",
      bg: "var(--color-success-dim)",
      label: "No Issues",
      icon: "✓",
    },
    low: {
      color: "var(--color-warning)",
      bg: "var(--color-warning-dim)",
      label: "Minor",
      icon: "⚠",
    },
    high: {
      color: "var(--color-danger)",
      bg: "var(--color-danger-dim)",
      label: "Critical",
      icon: "✕",
    },
  }[severity ?? "none"] ?? {
    color: "var(--color-text-dim)",
    bg: "rgba(239,243,244,0.04)",
    label: severity ?? "Unknown",
    icon: "?",
  };

  const fidelityConfig = {
    excellent: { color: "var(--color-success)", label: "Excellent" },
    average:   { color: "var(--color-warning)", label: "Average" },
    poor:      { color: "var(--color-danger)", label: "Poor" },
  }[pedagogicalFidelity ?? "average"] ?? { color: "var(--color-text-dim)", label: pedagogicalFidelity };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] p-4">
      <h4 className="text-[12px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Critic Review
      </h4>

      {/* Severity + Pass/Fail badge */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className="text-[13px] font-medium px-2 py-0.5 rounded-full"
            style={{ color: severityConfig.color, backgroundColor: severityConfig.bg }}
          >
            {severityConfig.icon} {severityConfig.label}
          </span>
        </div>
        {passed !== undefined && (
          <span
            className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
            style={{
              color: passed ? "var(--color-success)" : "var(--color-danger)",
              backgroundColor: passed ? "var(--color-success-dim)" : "var(--color-danger-dim)",
            }}
          >
            {passed ? "PASSED" : "FAILED"}
          </span>
        )}
      </div>

      {/* Metrics row */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        {pedagogicalFidelity && (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-[var(--color-text-dim)]">Pedagogy:</span>
            <span className="text-[11px] font-medium" style={{ color: fidelityConfig.color }}>
              {fidelityConfig.label}
            </span>
          </div>
        )}
        {isSocratic !== undefined && (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-[var(--color-text-dim)]">Socratic:</span>
            <span className="text-[11px] font-medium" style={{ color: isSocratic ? "var(--color-success)" : "var(--color-danger)" }}>
              {isSocratic ? "Yes" : "No"}
            </span>
          </div>
        )}
        {validatedCitations !== undefined && validatedCitations > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-[var(--color-text-dim)]">Citations:</span>
            <span className="text-[11px] font-medium text-[var(--color-text-main)]">
              {validatedCitations}
            </span>
          </div>
        )}
      </div>

      {/* Issues list */}
      {issues && issues.length > 0 && (
        <div className="mt-2">
          <p className="text-[11px] font-medium text-[var(--color-text-muted)] mb-1.5">Issues Found:</p>
          <ul className="space-y-1.5">
            {issues.map((issue, i) => (
              <li key={i} className="text-[11px] text-[var(--color-text-dim)] flex gap-1.5 leading-[1.5]">
                <span className="text-[var(--color-danger)] flex-shrink-0 mt-0.5">•</span>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Required facts */}
      {requiredFacts && requiredFacts.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
          <p className="text-[11px] font-medium text-[var(--color-text-muted)] mb-1.5">Required Corrections:</p>
          <ul className="space-y-1">
            {requiredFacts.map((fact, i) => (
              <li key={i} className="text-[11px] text-[var(--color-warning)] flex gap-1.5 leading-[1.5]">
                <span className="flex-shrink-0 mt-0.5">→</span>
                {fact}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function ObservabilityDrawer({
  isOpen,
  onClose,
  agentThoughts,
  retrievalLabel,
  retrievalMs,
  mermaidGraph,
  critic,
  activeNodes,
}: ObservabilityDrawerProps) {
  if (!isOpen) return null;

  const hasContent =
    retrievalLabel ||
    agentThoughts.length > 0 ||
    activeNodes.length > 0 ||
    mermaidGraph ||
    critic;

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

            {/* Live Execution Graph — streams with each node */}
            <LiveExecutionGraph
              agentThoughts={agentThoughts}
              activeNodes={activeNodes}
            />

            {/* Critic Review — mapped to actual CriticOutput schema */}
            {critic && Object.keys(critic).length > 0 && (
              <CriticReview critic={critic} />
            )}

          </>
        )}
      </div>
    </Drawer>
  );
}

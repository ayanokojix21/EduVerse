"use client";

// ─────────────────────────────────────────────────────────────────────────────
// KnowledgeUniverse — D3 force-directed graph visualization.
//
// Renders the student's topic mastery as an interactive node graph:
// - Nodes sized by `val` (knowledge depth)
// - Nodes colored by `score` (green → yellow → red)
// - Links connect related topics
// - Hover shows topic name and mastery percentage
// - Canvas-based for performance with large graphs
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";
import type { MasteryNode, MasteryLink } from "@/lib/types";

// ─── Props ───────────────────────────────────────────────────────────────────

interface KnowledgeUniverseProps {
  nodes: MasteryNode[];
  links: MasteryLink[];
}

// ─── Simulation Node/Link types ──────────────────────────────────────────────

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  val: number;
  score: number;
  color: string;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  source: string | SimNode;
  target: string | SimNode;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function KnowledgeUniverse({ nodes, links }: KnowledgeUniverseProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);

  // ── Resize handler ──────────────────────────────────────────────────────

  const getSize = useCallback(() => {
    if (!containerRef.current) return { width: 600, height: 400 };
    const rect = containerRef.current.getBoundingClientRect();
    return { width: rect.width, height: Math.max(rect.height, 400) };
  }, []);

  // ── Initialize simulation ───────────────────────────────────────────────

  useEffect(() => {
    if (!canvasRef.current || nodes.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = getSize();
    const dpr = window.devicePixelRatio || 1;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Build simulation data
    const simNodes: SimNode[] = nodes.map((n) => ({
      ...n,
      x: width / 2 + (Math.random() - 0.5) * 200,
      y: height / 2 + (Math.random() - 0.5) * 200,
    }));

    const simLinks: SimLink[] = links.map((l) => ({
      source: l.source,
      target: l.target,
    }));

    nodesRef.current = simNodes;
    linksRef.current = simLinks;

    // Create simulation
    const simulation = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(80)
          .strength(0.3)
      )
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((d) => d.val + 4)
      )
      .alphaDecay(0.02)
      .on("tick", draw);

    simulationRef.current = simulation;

    // ── Draw function ─────────────────────────────────────────────────────

    function draw() {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);

      // Draw links
      ctx.strokeStyle = "rgba(47, 51, 54, 0.6)";
      ctx.lineWidth = 1;
      for (const link of simLinks) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (source.x == null || target.x == null) continue;

        ctx.beginPath();
        ctx.moveTo(source.x, source.y!);
        ctx.lineTo(target.x, target.y!);
        ctx.stroke();
      }

      // Draw nodes
      for (const node of simNodes) {
        if (node.x == null || node.y == null) continue;

        // Outer glow
        const gradient = ctx.createRadialGradient(
          node.x,
          node.y,
          0,
          node.x,
          node.y,
          node.val + 8
        );
        gradient.addColorStop(0, node.color + "40");
        gradient.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.val + 8, 0, 2 * Math.PI);
        ctx.fillStyle = gradient;
        ctx.fill();

        // Main node
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Label (only for larger nodes)
        if (node.val >= 15) {
          ctx.fillStyle = "#E7E9EA";
          ctx.font = "600 10px Inter, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";

          const label =
            node.name.length > 12
              ? node.name.slice(0, 11) + "…"
              : node.name;
          ctx.fillText(label, node.x, node.y);
        }
      }
    }

    // ── Drag behavior ─────────────────────────────────────────────────────

    const canvasSelection = d3.select(canvas);

    function findNode(mx: number, my: number): SimNode | undefined {
      for (let i = simNodes.length - 1; i >= 0; i--) {
        const n = simNodes[i];
        if (n.x == null || n.y == null) continue;
        const dx = mx - n.x;
        const dy = my - n.y;
        if (dx * dx + dy * dy < n.val * n.val) return n;
      }
      return undefined;
    }

    let draggedNode: SimNode | null = null;

    canvasSelection
      .on("mousedown", (event: MouseEvent) => {
        const [mx, my] = d3.pointer(event, canvas);
        const node = findNode(mx, my);
        if (node) {
          draggedNode = node;
          node.fx = node.x;
          node.fy = node.y;
          simulation.alphaTarget(0.3).restart();
        }
      })
      .on("mousemove", (event: MouseEvent) => {
        const [mx, my] = d3.pointer(event, canvas);

        if (draggedNode) {
          draggedNode.fx = mx;
          draggedNode.fy = my;
        }

        // Tooltip
        const hovered = findNode(mx, my);
        if (hovered && tooltipRef.current) {
          tooltipRef.current.style.display = "block";
          tooltipRef.current.style.left = `${event.offsetX + 12}px`;
          tooltipRef.current.style.top = `${event.offsetY - 8}px`;
          tooltipRef.current.innerHTML = `
            <span style="font-weight:600;color:#E7E9EA">${hovered.name}</span>
            <br/>
            <span style="color:${hovered.color}">${(hovered.score * 100).toFixed(0)}% mastery</span>
          `;
          canvas.style.cursor = "pointer";
        } else if (tooltipRef.current) {
          tooltipRef.current.style.display = "none";
          canvas.style.cursor = "default";
        }
      })
      .on("mouseup", () => {
        if (draggedNode) {
          draggedNode.fx = null;
          draggedNode.fy = null;
          draggedNode = null;
          simulation.alphaTarget(0);
        }
      })
      .on("mouseleave", () => {
        if (tooltipRef.current) tooltipRef.current.style.display = "none";
      });

    // ── Cleanup ───────────────────────────────────────────────────────────

    return () => {
      simulation.stop();
      canvasSelection.on("mousedown", null).on("mousemove", null).on("mouseup", null).on("mouseleave", null);
    };
  }, [nodes, links, getSize]);

  // ── Empty state ─────────────────────────────────────────────────────────

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 rounded-full bg-[rgba(239,243,244,0.04)] flex items-center justify-center text-[28px] mb-4">
          🌌
        </div>
        <p className="text-[14px] text-[var(--color-text-muted)]">
          Your Knowledge Universe is empty
        </p>
        <p className="text-[12px] text-[var(--color-text-dim)] mt-1">
          Start chatting to build your topic mastery graph
        </p>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div
      ref={containerRef}
      className="
        relative w-full
        border border-[var(--color-border)]
        rounded-[var(--radius-xl)]
        bg-[var(--color-bg)]
        overflow-hidden
        animate-[fade-up_0.5s_ease-out_both]
      "
      style={{ minHeight: 400 }}
    >
      {/* Legend */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#4ade80]" />
          <span className="text-[10px] text-[var(--color-text-dim)]">High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#fbbf24]" />
          <span className="text-[10px] text-[var(--color-text-dim)]">Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#f87171]" />
          <span className="text-[10px] text-[var(--color-text-dim)]">Low</span>
        </div>
      </div>

      <canvas ref={canvasRef} className="w-full h-full" />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="
          absolute pointer-events-none
          bg-[var(--color-panel)] border border-[var(--color-border)]
          rounded-[var(--radius-md)]
          px-2.5 py-1.5
          text-[11px] leading-[1.5]
          shadow-[0_4px_16px_rgba(0,0,0,0.4)]
          z-20
        "
        style={{ display: "none" }}
      />
    </div>
  );
}

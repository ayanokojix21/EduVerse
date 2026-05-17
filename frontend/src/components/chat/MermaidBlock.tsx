"use client";

// ─────────────────────────────────────────────────────────────────────────────
// MermaidBlock — Renders Mermaid diagram syntax into an inline SVG.
//
// Uses the already-installed mermaid (v11) package.
// Client-side only — mermaid.render() requires DOM access.
// ─────────────────────────────────────────────────────────────────────────────

import { memo, useEffect, useRef, useState, useId } from "react";

let mermaidInitialized = false;

async function getMermaid() {
  const m = (await import("mermaid")).default;
  if (!mermaidInitialized) {
    m.initialize({
      startOnLoad: false,
      theme: "dark",
      themeVariables: {
        darkMode: true,
        background: "#16181C",
        primaryColor: "#1D9BF0",
        primaryTextColor: "#E7E9EA",
        primaryBorderColor: "rgba(255,255,255,0.12)",
        lineColor: "#536471",
        secondaryColor: "#1e2a3a",
        tertiaryColor: "#1a1e24",
        fontFamily: "'Inter', sans-serif",
        fontSize: "14px",
        nodeBorder: "rgba(255,255,255,0.15)",
        clusterBkg: "rgba(29,155,240,0.06)",
        clusterBorder: "rgba(29,155,240,0.2)",
        edgeLabelBackground: "#16181C",
        noteTextColor: "#E7E9EA",
        noteBkgColor: "#1e2a3a",
        noteBorderColor: "rgba(255,255,255,0.12)",
      },
    });
    mermaidInitialized = true;
  }
  return m;
}

// ─── Props ───────────────────────────────────────────────────────────────────

interface MermaidBlockProps {
  code: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export const MermaidBlock = memo(function MermaidBlock({ code }: MermaidBlockProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(true);
  const reactId = useId();
  // Create a DOM-safe ID from the React ID
  const mermaidId = `mermaid-${reactId.replace(/:/g, "-")}`;

  useEffect(() => {
    if (!code.trim() || !containerRef.current) return;

    let cancelled = false;

    (async () => {
      try {
        setRendering(true);
        setError(null);
        const mermaid = await getMermaid();
        const { svg } = await mermaid.render(mermaidId, code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to render diagram");
        }
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();

    return () => { cancelled = true; };
  }, [code, mermaidId]);

  if (error) {
    return (
      <div className="mermaid-container mermaid-error">
        <div className="mermaid-error-header">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>Diagram syntax error</span>
        </div>
        <pre className="mermaid-error-code"><code>{code}</code></pre>
      </div>
    );
  }

  return (
    <div className="mermaid-container">
      {rendering && (
        <div className="mermaid-loading">
          <span className="mermaid-loading-dot" />
          <span>Rendering diagram…</span>
        </div>
      )}
      <div ref={containerRef} className="mermaid-svg-wrapper" />
    </div>
  );
});

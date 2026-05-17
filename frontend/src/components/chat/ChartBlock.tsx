"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ChartBlock — Renders Chart.js JSON specs into interactive <canvas> charts.
//
// Expects a JSON string with Chart.js v4 format: {type, data, options?}
// Automatically applies the EduVerse dark theme.
// ─────────────────────────────────────────────────────────────────────────────

import { memo, useEffect, useRef, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  RadialLinearScale,
  Filler,
  Tooltip,
  Legend,
  Title,
} from "chart.js";

// Register all chart types we support
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  RadialLinearScale,
  Filler,
  Tooltip,
  Legend,
  Title
);

// ─── EduVerse Dark Theme Palette ─────────────────────────────────────────────

const CHART_COLORS = [
  "rgba(29, 155, 240, 0.85)",   // accent blue
  "rgba(0, 186, 124, 0.85)",    // success green
  "rgba(255, 212, 0, 0.85)",    // warning yellow
  "rgba(244, 33, 46, 0.85)",    // danger red
  "rgba(147, 130, 255, 0.85)",  // purple
  "rgba(255, 122, 0, 0.85)",    // orange
  "rgba(0, 209, 209, 0.85)",    // cyan
  "rgba(255, 105, 180, 0.85)",  // pink
];

const CHART_BORDERS = CHART_COLORS.map((c) => c.replace("0.85", "1"));

function applyThemeDefaults(config: Record<string, unknown>): Record<string, unknown> {
  const type = config.type as string;
  const data = config.data as Record<string, unknown> | undefined;

  // Auto-assign colors to datasets that don't have them
  if (data?.datasets && Array.isArray(data.datasets)) {
    data.datasets = data.datasets.map((ds: Record<string, unknown>, i: number) => {
      const color = CHART_COLORS[i % CHART_COLORS.length];
      const border = CHART_BORDERS[i % CHART_BORDERS.length];

      const isPie = type === "pie" || type === "doughnut" || type === "polarArea";
      return {
        backgroundColor: isPie ? CHART_COLORS.slice(0, (data.labels as string[])?.length ?? 4) : color,
        borderColor: isPie ? CHART_BORDERS.slice(0, (data.labels as string[])?.length ?? 4) : border,
        borderWidth: isPie ? 1 : 2,
        pointRadius: type === "line" ? 4 : undefined,
        pointHoverRadius: type === "line" ? 6 : undefined,
        tension: type === "line" ? 0.3 : undefined,
        fill: type === "radar" ? true : false,
        ...ds,
      };
    });
  }

  // Merge dark theme options
  const options = (config.options ?? {}) as Record<string, unknown>;
  const scales = (options.scales ?? {}) as Record<string, unknown>;

  const isRadial = type === "pie" || type === "doughnut" || type === "polarArea" || type === "radar";

  return {
    ...config,
    data,
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 600, easing: "easeOutQuart" as const },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: "#E7E9EA",
            font: { family: "'Inter', sans-serif", size: 12 },
            padding: 16,
            usePointStyle: true,
            pointStyleWidth: 10,
          },
        },
        tooltip: {
          backgroundColor: "rgba(22, 24, 28, 0.95)",
          titleColor: "#E7E9EA",
          bodyColor: "#71767B",
          borderColor: "rgba(255,255,255,0.12)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 10,
          titleFont: { family: "'Inter', sans-serif", size: 13, weight: "600" as const },
          bodyFont: { family: "'Inter', sans-serif", size: 12 },
        },
        ...(options.plugins as Record<string, unknown> ?? {}),
      },
      scales: isRadial
        ? undefined
        : {
            x: {
              ticks: { color: "#71767B", font: { family: "'Inter', sans-serif", size: 11 } },
              grid: { color: "rgba(255,255,255,0.04)", drawBorder: false },
              border: { display: false },
              ...(scales.x as Record<string, unknown> ?? {}),
            },
            y: {
              ticks: { color: "#71767B", font: { family: "'Inter', sans-serif", size: 11 } },
              grid: { color: "rgba(255,255,255,0.06)", drawBorder: false },
              border: { display: false },
              ...(scales.y as Record<string, unknown> ?? {}),
            },
          },
      ...options,
    },
  };
}

// ─── Props ───────────────────────────────────────────────────────────────────

interface ChartBlockProps {
  code: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export const ChartBlock = memo(function ChartBlock({ code }: ChartBlockProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<ChartJS | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    try {
      const parsed = JSON.parse(code.trim());
      if (!parsed.type || !parsed.data) {
        throw new Error("Chart JSON must include 'type' and 'data' fields.");
      }

      const config = applyThemeDefaults(parsed);

      // Destroy previous chart instance
      if (chartRef.current) {
        chartRef.current.destroy();
      }

      chartRef.current = new ChartJS(canvasRef.current, config as any);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid chart JSON");
    }

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [code]);

  if (error) {
    return (
      <div className="chart-container chart-error">
        <div className="chart-error-header">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>Chart rendering error: {error}</span>
        </div>
        <pre className="chart-error-code"><code>{code}</code></pre>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <canvas ref={canvasRef} />
    </div>
  );
});

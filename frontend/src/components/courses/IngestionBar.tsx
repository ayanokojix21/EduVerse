"use client";

// ─────────────────────────────────────────────────────────────────────────────
// IngestionBar — Thin progress bar that polls ingestion status.
// Polls GET /api/v1/ingestion/status/{courseId} every 3 seconds.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState, useCallback } from "react";
import { ingestionApi } from "@/lib/api";
import type { IngestionStatusValue } from "@/lib/types";

interface IngestionBarProps {
  courseId: string;
  /** Called when status changes */
  onStatusChange?: (status: IngestionStatusValue) => void;
}

const STATUS_COLORS: Record<IngestionStatusValue, string> = {
  completed: "#4ade80",
  processing: "#fbbf24",
  pending: "#fbbf24",
  failed: "#f87171",
  none: "#536471",
};

export function IngestionBar({ courseId, onStatusChange }: IngestionBarProps) {
  const [status, setStatus] = useState<IngestionStatusValue>("none");
  const [fileCount, setFileCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    try {
      const data = await ingestionApi.status(courseId);
      setStatus(data.status);
      setFileCount(data.current_file_count);
      setError(data.error ?? null);
      onStatusChange?.(data.status);

      // Stop polling if terminal state
      if (data.status === "completed" || data.status === "failed" || data.status === "none") {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch (err) {
      console.error("Ingestion poll error:", err);
    }
  }, [courseId, onStatusChange]);

  useEffect(() => {
    poll(); // Initial fetch
    intervalRef.current = setInterval(poll, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [poll]);

  if (status === "none") return null;

  const isActive = status === "processing" || status === "pending";
  const barColor = STATUS_COLORS[status];

  return (
    <div className="space-y-1">
      {/* Bar */}
      <div className="h-1 w-full bg-[rgba(239,243,244,0.06)] rounded-full overflow-hidden">
        <div
          className={`
            h-full rounded-full transition-all duration-500
            ${isActive ? "animate-[progress-indeterminate_1.5s_ease-in-out_infinite]" : ""}
          `}
          style={{
            backgroundColor: barColor,
            width: status === "completed" ? "100%" : isActive ? "60%" : "100%",
          }}
        />
      </div>

      {/* Label */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[var(--color-text-dim)] capitalize">
          {status === "processing" ? "Indexing…" : status}
        </span>
        <span className="text-[10px] text-[var(--color-text-dim)]">
          {fileCount} file{fileCount !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Error */}
      {error && status === "failed" && (
        <p className="text-[10px] text-[var(--color-danger)] truncate">{error}</p>
      )}
    </div>
  );
}

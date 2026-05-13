"use client";

// ─────────────────────────────────────────────────────────────────────────────
// TrainingControls — Trigger/distill training + status badge.
// Polls GET /api/v1/rl/train/status while training is running.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState, useCallback } from "react";
import { rlApi } from "@/lib/api";
import type { TrainingStatus } from "@/lib/types";

const STATUS_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  idle:     { color: "var(--color-text-dim)", bg: "rgba(239,243,244,0.04)", label: "Idle" },
  running:  { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", label: "Running" },
  complete: { color: "#4ade80", bg: "rgba(74,222,128,0.1)", label: "Complete" },
  error:    { color: "var(--color-danger)", bg: "var(--color-danger-dim)", label: "Error" },
};

export function TrainingControls() {
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isDistilling, setIsDistilling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Poll status ─────────────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    try {
      const data = await rlApi.trainingStatus();
      setStatus(data);

      // Stop polling on terminal state
      if (data.status !== "running" && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (err) {
      console.error("Training status poll error:", err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchStatus]);

  const startPolling = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(fetchStatus, 5000);
  };

  // ── Trigger training ────────────────────────────────────────────────────

  const handleTrigger = async () => {
    try {
      setIsTriggering(true);
      await rlApi.triggerTraining();
      setStatus({ status: "running", message: "Training triggered" });
      startPolling();
    } catch (err) {
      console.error("Failed to trigger training:", err);
    } finally {
      setIsTriggering(false);
    }
  };

  // ── Distill ─────────────────────────────────────────────────────────────

  const handleDistill = async () => {
    try {
      setIsDistilling(true);
      await rlApi.distill();
      setStatus({ status: "running", message: "Distillation triggered" });
      startPolling();
    } catch (err) {
      console.error("Failed to trigger distillation:", err);
    } finally {
      setIsDistilling(false);
    }
  };

  const isRunning = status?.status === "running";
  const statusStyle = STATUS_STYLES[status?.status ?? "idle"] ?? STATUS_STYLES.idle;

  return (
    <div className="border border-[var(--color-border)] rounded-[var(--radius-xl)] p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[14px] font-semibold text-[var(--color-text-main)]">
          Training Controls
        </h3>
        <span
          className="text-[11px] font-medium px-2.5 py-0.5 rounded-full"
          style={{ color: statusStyle.color, backgroundColor: statusStyle.bg }}
        >
          {isRunning && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-[pulse-fast_0.8s_ease-in-out_infinite]" />
          )}
          {statusStyle.label}
        </span>
      </div>

      {/* Status message */}
      {status?.message && (
        <p className="text-[12px] text-[var(--color-text-muted)] mb-3">
          {status.message}
        </p>
      )}

      {/* Timestamps */}
      {(status?.started_at || status?.completed_at) && (
        <div className="flex gap-4 mb-4 text-[11px] text-[var(--color-text-dim)]">
          {status.started_at && (
            <span>Started: {new Date(status.started_at).toLocaleString()}</span>
          )}
          {status.completed_at && (
            <span>Completed: {new Date(status.completed_at).toLocaleString()}</span>
          )}
        </div>
      )}

      {/* Buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleTrigger}
          disabled={isTriggering || isRunning}
          className="
            flex-1 flex items-center justify-center gap-2
            px-4 py-2.5
            rounded-[var(--radius-lg)]
            text-[12px] font-semibold
            bg-[var(--color-text-main)] text-black
            hover:bg-[rgba(239,243,244,0.85)]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-150
          "
        >
          {isTriggering ? (
            <div className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          )}
          {isTriggering ? "Starting…" : "Trigger Training"}
        </button>

        <button
          onClick={handleDistill}
          disabled={isDistilling || isRunning}
          className="
            flex items-center justify-center gap-2
            px-4 py-2.5
            rounded-[var(--radius-lg)]
            text-[12px] font-medium
            border border-[var(--color-border)]
            text-[var(--color-text-main)]
            hover:bg-[rgba(239,243,244,0.06)]
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-150
          "
        >
          {isDistilling ? (
            <div className="w-3.5 h-3.5 border-2 border-[var(--color-text-dim)] border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4" />
            </svg>
          )}
          Distill
        </button>
      </div>
    </div>
  );
}

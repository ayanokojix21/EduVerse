"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Loader — Skeleton pulser, progress bar, typing indicator
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";

// ── Skeleton Block ────────────────────────────────────────────────────────────

interface SkeletonProps {
  width?: string;
  height?: string;
  className?: string;
  rounded?: "sm" | "md" | "lg" | "full";
}

const roundedMap = {
  sm: "rounded",
  md: "rounded-lg",
  lg: "rounded-xl",
  full: "rounded-full",
};

export function Skeleton({ width = "100%", height = "1em", className = "", rounded = "md" }: SkeletonProps) {
  return (
    <div
      className={["skeleton-shimmer", roundedMap[rounded], className].join(" ")}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

// ── Skeleton Text Lines ───────────────────────────────────────────────────────

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={["flex flex-col gap-2", className].join(" ")} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          width={i === lines - 1 ? "60%" : "100%"}
          height="0.875rem"
        />
      ))}
    </div>
  );
}

// ── Skeleton Card ─────────────────────────────────────────────────────────────

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={[
        "p-4 border border-[#2F3336] rounded-xl bg-[#16181C]",
        "flex flex-col gap-3",
        className,
      ].join(" ")}
      aria-hidden="true"
    >
      <div className="flex items-center gap-3">
        <Skeleton width="2.5rem" height="2.5rem" rounded="full" />
        <div className="flex-1 flex flex-col gap-2">
          <Skeleton width="50%" height="0.875rem" />
          <Skeleton width="30%" height="0.75rem" />
        </div>
      </div>
      <SkeletonText lines={2} />
    </div>
  );
}

// ── Progress Bar ──────────────────────────────────────────────────────────────

interface ProgressBarProps {
  value: number;      // 0–100
  className?: string;
  color?: "primary" | "success" | "warning" | "danger";
  label?: string;
  animate?: boolean;
}

const progressColors = {
  primary: "bg-[#EFF3F4]",
  success: "bg-[#00BA7C]",
  warning: "bg-[#FFD400]",
  danger: "bg-[#F4212E]",
};

export function ProgressBar({ value, className = "", color = "primary", label, animate = false }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={["flex flex-col gap-1", className].join(" ")}>
      {label && (
        <div className="flex items-center justify-between text-[12px] text-[#71767B]">
          <span>{label}</span>
          <span>{clamped}%</span>
        </div>
      )}
      <div className="h-0.5 bg-[#2F3336] rounded-full overflow-hidden">
        <div
          className={[
            "h-full rounded-full transition-all duration-500",
            progressColors[color],
            animate ? "animate-pulse" : "",
          ].join(" ")}
          style={{ width: `${clamped}%` }}
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}

// ── Typing Indicator (3 bouncing dots) ───────────────────────────────────────

export function TypingIndicator({ className = "" }: { className?: string }) {
  return (
    <div
      className={["flex items-center gap-1 px-1", className].join(" ")}
      aria-label="AI is typing…"
      role="status"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-[#71767B] animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.9s" }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

// ── Full-page Spinner ─────────────────────────────────────────────────────────

export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-black">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-[#2F3336] border-t-[#EFF3F4] rounded-full animate-spin" />
        <span className="text-[13px] text-[#71767B]">Loading…</span>
      </div>
    </div>
  );
}

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Badge — Pill-shaped status badges
// Variants: default, success, warning, danger, muted
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "muted" | "classroom" | "local";

interface BadgeProps {
  variant?: BadgeVariant;
  dot?: boolean;          // Show a leading status dot
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, { badge: string; dot: string }> = {
  default: {
    badge: "bg-[rgba(239,243,244,0.1)] text-[#E7E9EA] border-[#2F3336]",
    dot: "bg-[#E7E9EA]",
  },
  success: {
    badge: "bg-[rgba(0,186,124,0.1)] text-[#00BA7C] border-[rgba(0,186,124,0.2)]",
    dot: "bg-[#00BA7C]",
  },
  warning: {
    badge: "bg-[rgba(255,212,0,0.1)] text-[#FFD400] border-[rgba(255,212,0,0.2)]",
    dot: "bg-[#FFD400]",
  },
  danger: {
    badge: "bg-[rgba(244,33,46,0.1)] text-[#F4212E] border-[rgba(244,33,46,0.2)]",
    dot: "bg-[#F4212E]",
  },
  muted: {
    badge: "bg-transparent text-[#71767B] border-[#2F3336]",
    dot: "bg-[#71767B]",
  },
  classroom: {
    badge: "bg-[rgba(66,133,244,0.1)] text-[#4285F4] border-[rgba(66,133,244,0.2)]",
    dot: "bg-[#4285F4]",
  },
  local: {
    badge: "bg-[rgba(239,243,244,0.06)] text-[#71767B] border-[#2F3336]",
    dot: "bg-[#71767B]",
  },
};

export function Badge({ variant = "default", dot = false, children, className = "" }: BadgeProps) {
  const styles = variantStyles[variant];

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5",
        "px-2 py-0.5 rounded-full",
        "text-[11px] font-medium tracking-wide",
        "border",
        styles.badge,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {dot && (
        <span
          className={["w-1.5 h-1.5 rounded-full flex-shrink-0", styles.dot].join(" ")}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}

// ─── Convenience exports for common use cases ─────────────────────────────────

export function IngestionDot({ status }: { status: "none" | "pending" | "processing" | "completed" | "failed" }) {
  const map: Record<string, BadgeVariant> = {
    none: "muted",
    pending: "warning",
    processing: "warning",
    completed: "success",
    failed: "danger",
  };

  const labels: Record<string, string> = {
    none: "Not indexed",
    pending: "Pending",
    processing: "Indexing…",
    completed: "Indexed",
    failed: "Failed",
  };

  return (
    <Badge variant={map[status] ?? "muted"} dot>
      {labels[status] ?? status}
    </Badge>
  );
}

export function SourceBadge({ source }: { source: "classroom" | "local" }) {
  return (
    <Badge variant={source === "classroom" ? "classroom" : "local"}>
      {source === "classroom" ? "Google Classroom" : "Local"}
    </Badge>
  );
}

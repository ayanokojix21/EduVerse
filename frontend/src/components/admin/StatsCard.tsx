"use client";

// ─────────────────────────────────────────────────────────────────────────────
// StatsCard — Large metric number with small label.
// Used on the RLAIF admin dashboard.
// ─────────────────────────────────────────────────────────────────────────────

interface StatsCardProps {
  label: string;
  value: string | number;
  /** Optional subtext (e.g., "vs last week") */
  subtext?: string;
  /** Accent color for the value */
  color?: string;
  /** Icon */
  icon?: React.ReactNode;
}

export function StatsCard({ label, value, subtext, color, icon }: StatsCardProps) {
  return (
    <div
      className="
        border border-[var(--color-border)]
        rounded-[var(--radius-xl)]
        bg-[var(--color-panel)]
        px-5 py-4
        transition-all duration-200
        hover:border-[var(--color-border-focus)]
        hover:bg-[rgba(239,243,244,0.02)]
      "
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
          {label}
        </span>
        {icon && (
          <span className="text-[var(--color-text-dim)]">{icon}</span>
        )}
      </div>

      <p
        className="text-[28px] font-bold leading-none tracking-tight"
        style={{ color: color ?? "var(--color-text-main)" }}
      >
        {value}
      </p>

      {subtext && (
        <p className="text-[11px] text-[var(--color-text-dim)] mt-1.5">
          {subtext}
        </p>
      )}
    </div>
  );
}

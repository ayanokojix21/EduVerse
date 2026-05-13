"use client";

// ─────────────────────────────────────────────────────────────────────────────
// StatStrip — Row of large stat numbers with small labels.
// Used on the profile page to display key metrics at a glance.
// ─────────────────────────────────────────────────────────────────────────────

interface Stat {
  label: string;
  value: string | number;
  /** Optional accent color for the value */
  color?: string;
}

interface StatStripProps {
  stats: Stat[];
}

export function StatStrip({ stats }: StatStripProps) {
  return (
    <div
      className="
        grid gap-4
        border border-[var(--color-border)]
        rounded-[var(--radius-xl)]
        bg-[var(--color-panel)]
        p-5
        animate-[fade-up_0.4s_ease-out_both]
      "
      style={{
        gridTemplateColumns: `repeat(${Math.min(stats.length, 5)}, 1fr)`,
      }}
    >
      {stats.map((stat, i) => (
        <div
          key={stat.label}
          className={`
            flex flex-col items-center text-center gap-1 py-1
            ${i > 0 ? "border-l border-[var(--color-border)]" : ""}
          `}
        >
          <span
            className="text-[28px] font-bold leading-none tracking-tight"
            style={{ color: stat.color ?? "var(--color-text-main)" }}
          >
            {stat.value}
          </span>
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
            {stat.label}
          </span>
        </div>
      ))}
    </div>
  );
}

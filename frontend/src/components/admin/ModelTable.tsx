"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ModelTable — RLAIF model registry table with monospace IDs.
// ─────────────────────────────────────────────────────────────────────────────

import type { RLModel } from "@/lib/types";

interface ModelTableProps {
  models: RLModel[];
  isLoading?: boolean;
}

const STATUS_CONFIG: Record<string, { color: string; bg: string }> = {
  active:   { color: "#4ade80", bg: "rgba(74,222,128,0.1)" },
  training: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)" },
  archived: { color: "#536471", bg: "rgba(83,100,113,0.1)" },
};

export function ModelTable({ models, isLoading = false }: ModelTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-[48px] rounded-[var(--radius-lg)] bg-[rgba(239,243,244,0.04)] animate-pulse" />
        ))}
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-[13px] text-[var(--color-text-dim)]">No models registered</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {["Model ID", "Name", "Version", "Role", "Status", "Created"].map((h) => (
              <th
                key={h}
                className="px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => {
            const status = STATUS_CONFIG[model.status] ?? STATUS_CONFIG.archived;
            return (
              <tr
                key={model.model_id}
                className="border-b border-[var(--color-border)] hover:bg-[rgba(239,243,244,0.03)] transition-colors"
              >
                <td className="px-3 py-3 text-[12px] font-mono text-[var(--color-text-muted)] truncate max-w-[140px]">
                  {model.model_id}
                </td>
                <td className="px-3 py-3 text-[13px] text-[var(--color-text-main)]">
                  {model.name}
                </td>
                <td className="px-3 py-3 text-[12px] font-mono text-[var(--color-text-muted)]">
                  v{model.version}
                </td>
                <td className="px-3 py-3">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-dim)]">
                    {model.role}
                  </span>
                </td>
                <td className="px-3 py-3">
                  <span
                    className="text-[11px] font-medium px-2 py-0.5 rounded-full capitalize"
                    style={{ color: status.color, backgroundColor: status.bg }}
                  >
                    {model.status}
                  </span>
                </td>
                <td className="px-3 py-3 text-[11px] text-[var(--color-text-dim)]">
                  {new Date(model.created_at).toLocaleDateString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

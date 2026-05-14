"use client";

// ─────────────────────────────────────────────────────────────────────────────
// RLAIF Admin Dashboard — /admin/rl
//
// Sections:
// 1. Stats overview (total episodes, avg reward, env version)
// 2. Training controls (trigger, distill, status)
// 3. Model registry table
// 4. Recent episodes list
// 5. DPO export link
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from "react";
import { rlApi } from "@/lib/api";
import type { RLStats, RLModel, RLEpisode } from "@/lib/types";
import { StatsCard } from "@/components/admin/StatsCard";
import { ModelTable } from "@/components/admin/ModelTable";
import { TrainingControls } from "@/components/admin/TrainingControls";
import { AuthGuard } from "@/components/layout/AuthGuard";

export default function RLAdminPage() {
  return (
    <AuthGuard requireAdmin>
      <RLAdminContent />
    </AuthGuard>
  );
}

function RLAdminContent() {
  const [stats, setStats] = useState<RLStats | null>(null);
  const [models, setModels] = useState<RLModel[]>([]);
  const [episodes, setEpisodes] = useState<RLEpisode[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      try {
        setIsLoading(true);
        const [statsRes, modelsRes, episodesRes] = await Promise.allSettled([
          rlApi.stats(),
          rlApi.models(),
          rlApi.episodes(),
        ]);
        if (statsRes.status === "fulfilled") setStats(statsRes.value);
        if (modelsRes.status === "fulfilled") setModels(modelsRes.value);
        if (episodesRes.status === "fulfilled") setEpisodes(episodesRes.value);
      } catch (err) {
        console.error("Failed to fetch RL data:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchAll();
  }, []);

  // ── Loading ─────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-[900px] mx-auto px-6 py-10 space-y-6">
        <div className="w-40 h-6 bg-[rgba(239,243,244,0.06)] rounded animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-[100px] rounded-[var(--radius-xl)] bg-[rgba(239,243,244,0.04)] animate-pulse" />
          ))}
        </div>
        <div className="h-[200px] rounded-[var(--radius-xl)] bg-[rgba(239,243,244,0.04)] animate-pulse" />
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="max-w-[900px] mx-auto px-6 py-10 space-y-8">
      {/* Header */}
      <div className="animate-[fade-up_0.3s_ease-out_both]">
        <h1 className="text-[22px] font-bold text-[var(--color-text-main)]">
          RLAIF Dashboard
        </h1>
        <p className="text-[13px] text-[var(--color-text-dim)] mt-0.5">
          Reinforcement Learning from AI Feedback — model management & training
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-[fade-up_0.4s_ease-out_both]">
          <StatsCard
            label="Total Episodes"
            value={stats.total_episodes.toLocaleString()}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" />
              </svg>
            }
          />
          <StatsCard
            label="Avg Reward"
            value={stats.average_reward.toFixed(3)}
            color={stats.average_reward >= 0.5 ? "#4ade80" : stats.average_reward >= 0 ? "#fbbf24" : "#f87171"}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            }
          />
          <StatsCard
            label="Environment"
            value={stats.environment_version}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
                <path d="M3 9h18" /><path d="M9 21V9" />
              </svg>
            }
          />
        </div>
      )}

      {/* Training Controls */}
      <div className="animate-[fade-up_0.45s_ease-out_both]">
        <TrainingControls />
      </div>

      {/* Model Registry */}
      <div className="animate-[fade-up_0.5s_ease-out_both]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[16px] font-semibold text-[var(--color-text-main)]">
            Model Registry
          </h2>
          <span className="text-[11px] text-[var(--color-text-dim)]">
            {models.length} model{models.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="border border-[var(--color-border)] rounded-[var(--radius-xl)] overflow-hidden">
          <ModelTable models={models} />
        </div>
      </div>

      {/* Recent Episodes */}
      <div className="animate-[fade-up_0.55s_ease-out_both]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[16px] font-semibold text-[var(--color-text-main)]">
            Recent Episodes
          </h2>
          <a
            href={rlApi.exportDpo()}
            target="_blank"
            rel="noopener noreferrer"
            className="
              flex items-center gap-1.5
              px-3 py-1.5
              rounded-full
              text-[11px] font-medium
              text-[var(--color-text-main)]
              border border-[var(--color-border)]
              hover:bg-[rgba(239,243,244,0.06)]
              transition-colors duration-150
            "
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export DPO
          </a>
        </div>

        {episodes.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-[13px] text-[var(--color-text-dim)]">No episodes recorded yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {episodes.slice(0, 20).map((ep) => (
              <div
                key={ep.episode_id}
                className="
                  border border-[var(--color-border)]
                  rounded-[var(--radius-lg)]
                  px-4 py-3
                  hover:bg-[rgba(239,243,244,0.03)]
                  transition-colors duration-100
                "
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] text-[var(--color-text-main)] line-clamp-1">
                      <span className="font-medium">Q:</span> {ep.query}
                    </p>
                    <p className="text-[12px] text-[var(--color-text-muted)] line-clamp-1 mt-0.5">
                      <span className="font-medium">A:</span> {ep.response}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span
                      className={`
                        text-[12px] font-semibold font-mono
                        ${ep.reward >= 0.5 ? "text-[#4ade80]" : ep.reward >= 0 ? "text-[#fbbf24]" : "text-[#f87171]"}
                      `}
                    >
                      {ep.reward >= 0 ? "+" : ""}{ep.reward.toFixed(3)}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-dim)]">
                      {new Date(ep.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

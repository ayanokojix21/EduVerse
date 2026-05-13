"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Profile Page — /profile
//
// Displays:
// - User info header (name, email, role)
// - StatStrip with key metrics
// - KnowledgeUniverse D3 force-directed graph
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { profileApi } from "@/lib/api";
import type {
  ProfileResponse,
  KnowledgeUniverseResponse,
} from "@/lib/types";
import { StatStrip } from "@/components/profile/StatStrip";
import { KnowledgeUniverse } from "@/components/profile/KnowledgeUniverse";

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [universe, setUniverse] = useState<KnowledgeUniverseResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setIsLoading(true);
        setError(null);

        const [profileData, universeData] = await Promise.allSettled([
          profileApi.get(),
          profileApi.universe(),
        ]);

        if (profileData.status === "fulfilled") {
          setProfile(profileData.value);
        }
        if (universeData.status === "fulfilled") {
          setUniverse(universeData.value);
        }
      } catch (err) {
        console.error("Failed to fetch profile:", err);
        setError("Failed to load profile data");
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, []);

  // ── Loading skeleton ────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-[800px] mx-auto px-6 py-10 space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-[rgba(239,243,244,0.06)] animate-pulse" />
          <div className="space-y-2">
            <div className="w-40 h-5 bg-[rgba(239,243,244,0.06)] rounded animate-pulse" />
            <div className="w-56 h-3 bg-[rgba(239,243,244,0.04)] rounded animate-pulse" />
          </div>
        </div>
        {/* Stats skeleton */}
        <div className="h-[88px] bg-[rgba(239,243,244,0.04)] rounded-[var(--radius-xl)] animate-pulse" />
        {/* Graph skeleton */}
        <div className="h-[400px] bg-[rgba(239,243,244,0.04)] rounded-[var(--radius-xl)] animate-pulse" />
      </div>
    );
  }

  // ── Error state ─────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center">
          <p className="text-[var(--color-danger)] text-[14px] mb-2">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-[13px] text-[var(--color-text-muted)] underline underline-offset-2 hover:text-[var(--color-text-main)]"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Compute stats ───────────────────────────────────────────────────────

  const topicCount = profile?.topic_mastery
    ? Object.keys(profile.topic_mastery).length
    : 0;

  const avgMastery = profile?.topic_mastery
    ? Object.values(profile.topic_mastery).length > 0
      ? (
          Object.values(profile.topic_mastery).reduce((a, b) => a + b, 0) /
          Object.values(profile.topic_mastery).length
        )
      : 0
    : 0;

  const stats = [
    {
      label: "Documents",
      value: profile?.total_documents ?? 0,
    },
    {
      label: "Sessions",
      value: profile?.actual_session_count ?? 0,
    },
    {
      label: "Topics",
      value: topicCount,
      color: "var(--color-primary)",
    },
    {
      label: "Avg Mastery",
      value: `${(avgMastery * 100).toFixed(0)}%`,
      color:
        avgMastery >= 0.7
          ? "#4ade80"
          : avgMastery >= 0.4
          ? "#fbbf24"
          : "#f87171",
    },
  ];

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="max-w-[800px] mx-auto px-6 py-10 space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4 animate-[fade-up_0.3s_ease-out_both]">
        {/* Avatar */}
        <div
          className="
            w-16 h-16 rounded-full
            bg-gradient-to-br from-[rgba(239,243,244,0.12)] to-[rgba(239,243,244,0.04)]
            flex items-center justify-center
            text-[24px] font-bold text-[var(--color-text-main)]
            border border-[var(--color-border)]
          "
        >
          {(profile?.full_name ?? user?.email ?? "U").charAt(0).toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <h1 className="text-[20px] font-bold text-[var(--color-text-main)] truncate">
            {profile?.full_name ?? user?.email ?? "Student"}
          </h1>
          <p className="text-[13px] text-[var(--color-text-muted)] truncate">
            {profile?.email ?? user?.email}
          </p>
          {user?.role && (
            <span
              className={`
                inline-block mt-1.5
                text-[10px] font-medium uppercase tracking-wider
                px-2 py-0.5 rounded-full
                ${
                  user.role === "admin"
                    ? "bg-[var(--color-warning-dim)] text-[var(--color-warning)]"
                    : "bg-[rgba(239,243,244,0.06)] text-[var(--color-text-dim)]"
                }
              `}
            >
              {user.role}
            </span>
          )}
        </div>

        {/* Joined date */}
        {profile?.created_at && (
          <div className="text-right hidden sm:block">
            <p className="text-[11px] text-[var(--color-text-dim)] uppercase tracking-wider">
              Joined
            </p>
            <p className="text-[13px] text-[var(--color-text-muted)]">
              {new Date(profile.created_at).toLocaleDateString(undefined, {
                month: "short",
                year: "numeric",
              })}
            </p>
          </div>
        )}
      </div>

      {/* Stats */}
      <StatStrip stats={stats} />

      {/* Knowledge Universe */}
      <div className="animate-[fade-up_0.6s_ease-out_both]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[16px] font-semibold text-[var(--color-text-main)]">
            Knowledge Universe
          </h2>
          <span className="text-[11px] text-[var(--color-text-dim)]">
            Drag nodes · Hover for details
          </span>
        </div>

        <KnowledgeUniverse
          nodes={universe?.nodes ?? []}
          links={universe?.links ?? []}
        />
      </div>

      {/* Topic mastery list (simple fallback / detail) */}
      {profile?.topic_mastery && Object.keys(profile.topic_mastery).length > 0 && (
        <div className="animate-[fade-up_0.7s_ease-out_both]">
          <h2 className="text-[16px] font-semibold text-[var(--color-text-main)] mb-3">
            Topic Breakdown
          </h2>
          <div className="space-y-2">
            {Object.entries(profile.topic_mastery)
              .sort(([, a], [, b]) => b - a)
              .map(([topic, score]) => (
                <div
                  key={topic}
                  className="
                    flex items-center gap-3
                    px-4 py-2.5
                    rounded-[var(--radius-lg)]
                    border border-[var(--color-border)]
                    bg-[var(--color-panel)]
                  "
                >
                  <span className="flex-1 text-[13px] text-[var(--color-text-main)] truncate">
                    {topic}
                  </span>

                  {/* Progress bar */}
                  <div className="w-24 h-1.5 bg-[rgba(239,243,244,0.06)] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${score * 100}%`,
                        backgroundColor:
                          score >= 0.7
                            ? "#4ade80"
                            : score >= 0.4
                            ? "#fbbf24"
                            : "#f87171",
                      }}
                    />
                  </div>

                  <span
                    className="text-[12px] font-medium w-10 text-right"
                    style={{
                      color:
                        score >= 0.7
                          ? "#4ade80"
                          : score >= 0.4
                          ? "#fbbf24"
                          : "#f87171",
                    }}
                  >
                    {(score * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

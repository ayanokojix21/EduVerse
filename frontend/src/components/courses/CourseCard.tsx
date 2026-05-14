"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CourseCard — Flat card for the dashboard bento grid.
//
// Features:
// - Source badge (Classroom / Local)
// - Ingestion status dot (green/yellow/red/gray)
// - Assignment count
// - Hover glow effect
// - Click opens the course drawer
// - "Chat" button navigates to the chat page
// ─────────────────────────────────────────────────────────────────────────────

import Link from "next/link";
import type { UnifiedCourse } from "@/lib/types";
import { IngestionDot, SourceBadge } from "@/components/ui/Badge";

interface CourseCardProps {
  course: UnifiedCourse;
  ingestionStatus?: "none" | "pending" | "processing" | "completed" | "failed";
  onClick: () => void;
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  completed:  { color: "#4ade80", label: "Indexed" },
  processing: { color: "#fbbf24", label: "Processing" },
  pending:    { color: "#fbbf24", label: "Pending" },
  failed:     { color: "#f87171", label: "Failed" },
  none:       { color: "#536471", label: "Not indexed" },
};

export function CourseCard({ course, ingestionStatus = "none", onClick }: CourseCardProps) {
  const status = STATUS_CONFIG[ingestionStatus] ?? STATUS_CONFIG.none;

  return (
    <div
      onClick={onClick}
      className="
        relative group cursor-pointer
        bg-black
        border border-[var(--color-border)]
        rounded-[var(--radius-xl)]
        p-5
        transition-all duration-200
        hover:border-[var(--color-border-focus)]
        hover:bg-[rgba(239,243,244,0.03)]
        hover:shadow-[0_0_24px_rgba(239,243,244,0.04)]
        animate-[fade-up_0.3s_ease-out_both]
      "
    >
      {/* Top row: Source badge + Status dot */}
      <div className="flex items-center justify-between mb-3">
        <SourceBadge source={course.source as "classroom" | "local"} />
        <IngestionDot status={ingestionStatus} />
      </div>

      {/* Course name */}
      <h3 className="text-[15px] font-semibold text-[var(--color-text-main)] truncate mb-1 group-hover:text-white transition-colors">
        {course.name}
      </h3>

      {/* Description */}
      {course.description && (
        <p className="text-[12px] text-[var(--color-text-muted)] line-clamp-2 leading-[1.5] mb-3">
          {course.description}
        </p>
      )}

      {/* Bottom row: Assignments + Chat link */}
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-[var(--color-border)]">
        <span className="text-[11px] text-[var(--color-text-dim)]">
          {course.assignment_count} assignment{course.assignment_count !== 1 ? "s" : ""}
        </span>

        <Link
          href={`/chat/${course.id}`}
          onClick={(e) => e.stopPropagation()}
          className="
            flex items-center gap-1.5
            px-3 py-1.5
            rounded-full
            text-[11px] font-medium
            text-[var(--color-text-main)]
            border border-[var(--color-border)]
            hover:bg-[rgba(239,243,244,0.08)]
            transition-colors duration-150
          "
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          Chat
        </Link>
      </div>
    </div>
  );
}

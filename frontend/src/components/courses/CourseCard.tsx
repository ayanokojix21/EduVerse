"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CourseCard — Premium card for the dashboard bento grid.
//
// Features:
// - Source badge (Classroom / Local)
// - Ingestion status dot (green/yellow/red/gray)
// - Assignment count
// - Hover glow effect with gradient border
// - Click opens the course drawer
// - "Chat" button navigates to the chat page
// ─────────────────────────────────────────────────────────────────────────────

import Link from "next/link";
import type { UnifiedCourse } from "@/lib/types";
import { IngestionDot, SourceBadge } from "@/components/ui/Badge";

interface CourseCardProps {
  course: UnifiedCourse;
  ingestionStatus?: "none" | "pending" | "processing" | "completed" | "failed";
  onClick?: () => void;
}

const COURSE_GRADIENTS = [
  "linear-gradient(135deg, rgba(29,155,240,0.15) 0%, rgba(29,155,240,0.03) 100%)",
  "linear-gradient(135deg, rgba(0,186,124,0.15) 0%, rgba(0,186,124,0.03) 100%)",
  "linear-gradient(135deg, rgba(255,212,0,0.12) 0%, rgba(255,212,0,0.03) 100%)",
  "linear-gradient(135deg, rgba(120,86,255,0.15) 0%, rgba(120,86,255,0.03) 100%)",
  "linear-gradient(135deg, rgba(249,24,128,0.12) 0%, rgba(249,24,128,0.03) 100%)",
  "linear-gradient(135deg, rgba(255,122,0,0.12) 0%, rgba(255,122,0,0.03) 100%)",
];

function getGradient(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return COURSE_GRADIENTS[Math.abs(hash) % COURSE_GRADIENTS.length];
}

export function CourseCard({ course, ingestionStatus = "none", onClick }: CourseCardProps) {
  const gradient = getGradient(course.name);

  return (
    <div
      onClick={onClick}
      className="card-glow relative group cursor-pointer animate-[fade-up_0.3s_ease-out_both]"
      style={{
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)',
        padding: '1.25rem',
        transition: 'all 0.3s ease',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget;
        el.style.borderColor = 'var(--color-border-focus)';
        el.style.boxShadow = '0 0 30px rgba(239,243,244,0.04)';
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget;
        el.style.borderColor = 'var(--color-border)';
        el.style.boxShadow = 'none';
      }}
    >
      {/* Gradient accent strip */}
      <div
        className="absolute top-0 left-0 right-0 h-[3px] rounded-t-[var(--radius-xl)] opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{ background: gradient }}
      />

      {/* Top row: Source badge + Status dot */}
      <div className="flex items-center justify-between mb-3">
        <SourceBadge source={course.source as "classroom" | "local"} />
        <IngestionDot status={ingestionStatus} />
      </div>

      {/* Course name */}
      <h3 className="text-[15px] font-semibold text-[var(--color-text-main)] truncate mb-1 group-hover:text-white transition-colors duration-200">
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
        <span className="text-[11px] text-[var(--color-text-dim)] flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
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
            hover:border-[var(--color-border-focus)]
            transition-all duration-200
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

"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard Page — /dashboard
//
// Bento grid of course cards with:
// - Fetch from GET /api/v1/courses/
// - "+ New Workspace" button → CreateCourseModal
// - Card click → CourseDrawer
// - Ingestion status polling per course
// ─────────────────────────────────────────────────────────────────────────────

import { useCallback, useEffect, useState } from "react";
import { coursesApi, ingestionApi } from "@/lib/api";
import type { UnifiedCourse, IngestionStatusValue } from "@/lib/types";
import { CourseCard } from "@/components/courses/CourseCard";
import { CourseDrawer } from "@/components/courses/CourseDrawer";
import { CreateCourseModal } from "@/components/courses/CreateCourseModal";

export default function DashboardPage() {
  const [courses, setCourses] = useState<UnifiedCourse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingestion status per course
  const [statuses, setStatuses] = useState<Record<string, IngestionStatusValue>>({});

  // UI state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState<UnifiedCourse | null>(null);

  // ── Fetch courses ───────────────────────────────────────────────────────

  const fetchCourses = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await coursesApi.list();
      setCourses(data);

      // Fetch ingestion statuses in parallel
      const statusEntries = await Promise.allSettled(
        data.map(async (c) => {
          const s = await ingestionApi.status(c.id);
          return [c.id, s.status] as [string, IngestionStatusValue];
        })
      );
      const statusMap: Record<string, IngestionStatusValue> = {};
      for (const entry of statusEntries) {
        if (entry.status === "fulfilled") {
          statusMap[entry.value[0]] = entry.value[1];
        }
      }
      setStatuses(statusMap);
    } catch (err) {
      console.error("Failed to fetch courses:", err);
      setError("Failed to load courses");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleCourseCreated = (course: UnifiedCourse) => {
    setCourses((prev) => [course, ...prev]);
    setStatuses((prev) => ({ ...prev, [course.id]: "none" }));
  };

  const handleCourseDeleted = () => {
    if (selectedCourse) {
      setCourses((prev) => prev.filter((c) => c.id !== selectedCourse.id));
      setSelectedCourse(null);
    }
  };

  // ── Loading skeleton ────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-[1100px] mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div className="w-40 h-6 bg-[rgba(239,243,244,0.06)] rounded animate-pulse" />
          <div className="w-32 h-9 bg-[rgba(239,243,244,0.06)] rounded-full animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="h-[160px] rounded-[var(--radius-xl)] bg-[rgba(239,243,244,0.04)] animate-pulse"
            />
          ))}
        </div>
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
            onClick={fetchCourses}
            className="text-[13px] text-[var(--color-text-muted)] underline underline-offset-2 hover:text-[var(--color-text-main)]"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 animate-[fade-up_0.3s_ease-out_both]">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--color-text-main)]">
            Dashboard
          </h1>
          <p className="text-[13px] text-[var(--color-text-dim)] mt-0.5">
            {courses.length} workspace{courses.length !== 1 ? "s" : ""}
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="
            flex items-center gap-2
            px-4 py-2.5
            rounded-full
            text-[13px] font-semibold
            bg-[var(--color-text-main)] text-black
            hover:bg-[rgba(239,243,244,0.85)]
            transition-all duration-150
          "
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New Workspace
        </button>
      </div>

      {/* Course grid */}
      {courses.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center animate-[fade-up_0.4s_ease-out_both]">
          <div className="w-16 h-16 rounded-full bg-[rgba(239,243,244,0.04)] flex items-center justify-center text-[28px] mb-4">
            📚
          </div>
          <p className="text-[15px] text-[var(--color-text-muted)] mb-1">
            No workspaces yet
          </p>
          <p className="text-[13px] text-[var(--color-text-dim)] mb-6">
            Create a local workspace or connect Google Classroom
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="
              flex items-center gap-2
              px-5 py-2.5
              rounded-full
              text-[13px] font-semibold
              border border-[var(--color-border)]
              text-[var(--color-text-main)]
              hover:bg-[rgba(239,243,244,0.06)]
              transition-all duration-150
            "
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Create your first workspace
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course, i) => (
            <div
              key={course.id}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <CourseCard
                course={course}
                ingestionStatus={statuses[course.id]}
                onClick={() => setSelectedCourse(course)}
              />
            </div>
          ))}
        </div>
      )}

      {/* Create Course Modal */}
      <CreateCourseModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleCourseCreated}
      />

      {/* Course Drawer */}
      {selectedCourse && (
        <CourseDrawer
          course={selectedCourse}
          isOpen={!!selectedCourse}
          onClose={() => setSelectedCourse(null)}
          onDeleted={handleCourseDeleted}
        />
      )}
    </div>
  );
}

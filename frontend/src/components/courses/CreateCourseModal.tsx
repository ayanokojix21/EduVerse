"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CreateCourseModal — Form to create a new local workspace.
// Name + optional description → POST /api/v1/courses/
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";
import { coursesApi } from "@/lib/api";
import type { UnifiedCourse } from "@/lib/types";

interface CreateCourseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (course: UnifiedCourse) => void;
}

export function CreateCourseModal({
  isOpen,
  onClose,
  onCreated,
}: CreateCourseModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    try {
      setIsSubmitting(true);
      setError(null);
      const course = await coursesApi.create({
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onCreated(course);
      setName("");
      setDescription("");
      onClose();
    } catch (err) {
      console.error("Failed to create course:", err);
      setError(err instanceof Error ? err.message : "Failed to create workspace");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      onClick={handleBackdropClick}
      className="
        fixed inset-0 z-50
        bg-black/60 backdrop-blur-[2px]
        flex items-center justify-center
        animate-[fade-in_0.15s_ease-out]
      "
    >
      <div
        className="
          w-full max-w-[440px] mx-4
          bg-[var(--color-panel)]
          border border-[var(--color-border)]
          rounded-[var(--radius-xl)]
          shadow-[0_8px_48px_rgba(0,0,0,0.6)]
          animate-[fade-up_0.2s_ease-out]
        "
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <h2 className="text-[16px] font-semibold text-[var(--color-text-main)]">
            New Workspace
          </h2>
          <button
            onClick={onClose}
            className="
              w-7 h-7 rounded-full
              flex items-center justify-center
              text-[var(--color-text-dim)]
              hover:bg-[rgba(239,243,244,0.08)]
              transition-colors duration-150
            "
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label
              htmlFor="course-name"
              className="block text-[12px] font-medium text-[var(--color-text-muted)] mb-1.5"
            >
              Workspace Name
            </label>
            <input
              id="course-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., CS 101 Study Notes"
              maxLength={100}
              autoFocus
              required
              className="
                w-full px-3 py-2.5
                bg-transparent
                border border-[var(--color-border)]
                rounded-[var(--radius-lg)]
                text-[14px] text-[var(--color-text-main)]
                placeholder:text-[var(--color-text-dim)]
                outline-none
                focus:border-[var(--color-border-focus)]
                transition-colors duration-150
              "
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="course-desc"
              className="block text-[12px] font-medium text-[var(--color-text-muted)] mb-1.5"
            >
              Description <span className="text-[var(--color-text-dim)]">(optional)</span>
            </label>
            <textarea
              id="course-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A brief description of this workspace"
              rows={3}
              maxLength={500}
              className="
                w-full px-3 py-2.5
                bg-transparent
                border border-[var(--color-border)]
                rounded-[var(--radius-lg)]
                text-[14px] text-[var(--color-text-main)]
                placeholder:text-[var(--color-text-dim)]
                outline-none resize-none
                focus:border-[var(--color-border-focus)]
                transition-colors duration-150
              "
            />
          </div>

          {/* Error */}
          {error && (
            <p className="text-[12px] text-[var(--color-danger)]">{error}</p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="
                px-4 py-2
                rounded-full
                text-[13px] font-medium
                text-[var(--color-text-muted)]
                hover:bg-[rgba(239,243,244,0.06)]
                transition-colors duration-150
              "
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isSubmitting}
              className="
                px-5 py-2
                rounded-full
                text-[13px] font-semibold
                bg-[var(--color-text-main)] text-black
                hover:bg-[rgba(239,243,244,0.85)]
                disabled:opacity-40 disabled:cursor-not-allowed
                transition-all duration-150
              "
            >
              {isSubmitting ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

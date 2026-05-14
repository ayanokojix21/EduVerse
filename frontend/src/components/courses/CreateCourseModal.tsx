"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CreateCourseModal — Form to create a new local workspace.
// Name + optional description → POST /api/v1/courses/
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";
import { coursesApi } from "@/lib/api";
import type { UnifiedCourse } from "@/lib/types";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

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

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="New Workspace"
      size="sm"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
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
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!name.trim()}
            loading={isSubmitting}
          >
            Create
          </Button>
        </div>
      </form>
    </Modal>
  );
}

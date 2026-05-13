"use client";

// ─────────────────────────────────────────────────────────────────────────────
// CourseDrawer — Right-side slide-in panel for course management.
//
// Tabs:
// 1. Files — Upload files, view FileList, trigger ingestion
// 2. Assignments — Fetch coursework from Classroom
//
// Actions: Upload, Sync from Classroom, Delete index
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useRef, useCallback } from "react";
import { ingestionApi, coursesApi } from "@/lib/api";
import type { UnifiedCourse, Coursework } from "@/lib/types";
import { FileList } from "./FileList";
import { IngestionBar } from "./IngestionBar";

interface CourseDrawerProps {
  course: UnifiedCourse;
  isOpen: boolean;
  onClose: () => void;
  onDeleted?: () => void;
}

const ACCEPTED_TYPES = ".pdf,.txt,.md,.docx";
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

export function CourseDrawer({ course, isOpen, onClose, onDeleted }: CourseDrawerProps) {
  const [activeTab, setActiveTab] = useState<"files" | "assignments">("files");
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [coursework, setCoursework] = useState<Coursework[]>([]);
  const [courseworkLoaded, setCourseworkLoaded] = useState(false);
  const [courseworkLoading, setCourseworkLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // ── File Upload ─────────────────────────────────────────────────────────

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_FILE_SIZE) {
      setUploadError("File exceeds 100 MB limit");
      return;
    }

    try {
      setIsUploading(true);
      setUploadError(null);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("course_id", course.id);
      await ingestionApi.upload(formData);
      // Trigger re-ingestion after upload
      await ingestionApi.trigger(course.id);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Sync from Classroom ────────────────────────────────────────────────

  const handleSync = async () => {
    try {
      setIsSyncing(true);
      await ingestionApi.sync(course.id);
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setIsSyncing(false);
    }
  };

  // ── Delete Course ──────────────────────────────────────────────────────

  const handleDeleteCourse = async () => {
    if (!confirm("Are you sure? This will delete the course and all indexed data.")) return;
    try {
      setIsDeleting(true);
      await coursesApi.delete(course.id);
      onDeleted?.();
      onClose();
    } catch (err) {
      console.error("Failed to delete course:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  // ── Load Coursework ────────────────────────────────────────────────────

  const loadCoursework = useCallback(async () => {
    if (courseworkLoaded) return;
    try {
      setCourseworkLoading(true);
      const data = await coursesApi.coursework(course.id);
      setCoursework(data);
      setCourseworkLoaded(true);
    } catch (err) {
      console.error("Failed to load coursework:", err);
    } finally {
      setCourseworkLoading(false);
    }
  }, [course.id, courseworkLoaded]);

  const handleTabChange = (tab: "files" | "assignments") => {
    setActiveTab(tab);
    if (tab === "assignments") loadCoursework();
  };

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="
          fixed right-0 top-0 bottom-0
          w-full max-w-[420px] z-50
          bg-[var(--color-bg)]
          border-l border-[var(--color-border)]
          flex flex-col
          animate-[slide-in-right_0.3s_ease-out_both]
        "
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)] flex-shrink-0">
          <div className="min-w-0 flex-1">
            <h2 className="text-[16px] font-semibold text-[var(--color-text-main)] truncate">
              {course.name}
            </h2>
            <span
              className={`
                text-[10px] font-semibold uppercase tracking-wider
                ${course.source === "classroom" ? "text-[#1d9bf0]" : "text-[var(--color-text-dim)]"}
              `}
            >
              {course.source}
            </span>
          </div>
          <button
            onClick={onClose}
            className="
              w-8 h-8 rounded-full flex-shrink-0
              flex items-center justify-center
              text-[var(--color-text-dim)]
              hover:bg-[rgba(239,243,244,0.08)]
              transition-colors duration-150
            "
            aria-label="Close drawer"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Ingestion bar */}
        <div className="px-5 pt-3">
          <IngestionBar courseId={course.id} />
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--color-border)] px-5 mt-2">
          {(["files", "assignments"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={`
                flex-1 py-2.5
                text-[13px] font-medium capitalize
                transition-colors duration-150
                border-b-2
                ${
                  activeTab === tab
                    ? "text-[var(--color-text-main)] border-[var(--color-text-main)]"
                    : "text-[var(--color-text-dim)] border-transparent hover:text-[var(--color-text-muted)]"
                }
              `}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {activeTab === "files" ? (
            <div className="space-y-4">
              {/* Upload + Sync buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="
                    flex-1 flex items-center justify-center gap-2
                    px-3 py-2.5
                    rounded-[var(--radius-lg)]
                    text-[12px] font-medium
                    border border-[var(--color-border)]
                    text-[var(--color-text-main)]
                    hover:bg-[rgba(239,243,244,0.06)]
                    disabled:opacity-40
                    transition-colors duration-150
                  "
                >
                  {isUploading ? (
                    <div className="w-3.5 h-3.5 border-2 border-[var(--color-text-dim)] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  )}
                  {isUploading ? "Uploading…" : "Upload File"}
                </button>

                {course.source === "classroom" && (
                  <button
                    onClick={handleSync}
                    disabled={isSyncing}
                    className="
                      flex items-center justify-center gap-2
                      px-3 py-2.5
                      rounded-[var(--radius-lg)]
                      text-[12px] font-medium
                      border border-[var(--color-border)]
                      text-[#1d9bf0]
                      hover:bg-[rgba(29,155,240,0.08)]
                      disabled:opacity-40
                      transition-colors duration-150
                    "
                  >
                    {isSyncing ? (
                      <div className="w-3.5 h-3.5 border-2 border-[#1d9bf0] border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21.5 2v6h-6" />
                        <path d="M2.5 22v-6h6" />
                        <path d="M2 11.5a10 10 0 0 1 18.8-4.3" />
                        <path d="M22 12.5a10 10 0 0 1-18.8 4.2" />
                      </svg>
                    )}
                    Sync
                  </button>
                )}
              </div>

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_TYPES}
                onChange={handleFileSelect}
                className="hidden"
              />

              {/* Upload error */}
              {uploadError && (
                <p className="text-[11px] text-[var(--color-danger)]">{uploadError}</p>
              )}

              {/* File list */}
              <FileList courseId={course.id} />
            </div>
          ) : (
            /* Assignments tab */
            <div>
              {courseworkLoading ? (
                <div className="space-y-2">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-[60px] rounded-[var(--radius-lg)] bg-[rgba(239,243,244,0.04)] animate-pulse" />
                  ))}
                </div>
              ) : coursework.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-[13px] text-[var(--color-text-dim)]">
                    {course.source === "classroom"
                      ? "No coursework found"
                      : "Coursework is only available for Classroom courses"}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {coursework.map((cw) => (
                    <div
                      key={cw.id}
                      className="
                        px-3 py-3
                        rounded-[var(--radius-lg)]
                        border border-[var(--color-border)]
                        hover:bg-[rgba(239,243,244,0.03)]
                        transition-colors duration-100
                      "
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-[var(--color-text-main)] truncate">
                            {cw.title}
                          </p>
                          {cw.description && (
                            <p className="text-[11px] text-[var(--color-text-muted)] line-clamp-2 mt-0.5 leading-[1.4]">
                              {cw.description}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1.5">
                            {cw.work_type && (
                              <span className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider">
                                {cw.work_type}
                              </span>
                            )}
                            {cw.due_date && (
                              <span className="text-[10px] text-[var(--color-text-dim)]">
                                Due {new Date(cw.due_date).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>

                        {cw.alternate_link && (
                          <a
                            href={cw.alternate_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="
                              w-6 h-6 rounded-full flex-shrink-0
                              flex items-center justify-center
                              text-[var(--color-text-dim)]
                              hover:text-[var(--color-text-main)]
                              hover:bg-[rgba(239,243,244,0.06)]
                              transition-colors duration-150
                            "
                            aria-label="Open in Classroom"
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                              <polyline points="15 3 21 3 21 9" />
                              <line x1="10" y1="14" x2="21" y2="3" />
                            </svg>
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer: Delete course */}
        <div className="border-t border-[var(--color-border)] px-5 py-3 flex-shrink-0">
          <button
            onClick={handleDeleteCourse}
            disabled={isDeleting}
            className="
              w-full flex items-center justify-center gap-2
              px-3 py-2
              rounded-[var(--radius-lg)]
              text-[12px] font-medium
              text-[var(--color-danger)]
              hover:bg-[var(--color-danger-dim)]
              disabled:opacity-40
              transition-colors duration-150
            "
          >
            {isDeleting ? (
              <div className="w-3.5 h-3.5 border-2 border-[var(--color-danger)] border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              </svg>
            )}
            {isDeleting ? "Deleting…" : "Delete Course"}
          </button>
        </div>
      </div>
    </>
  );
}

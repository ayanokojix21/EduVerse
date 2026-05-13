"use client";

// ─────────────────────────────────────────────────────────────────────────────
// FileList — Table of ingested files with delete actions.
// Fetches from GET /api/v1/ingestion/{courseId}/files
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState, useCallback } from "react";
import { ingestionApi } from "@/lib/api";
import type { IngestedFile } from "@/lib/types";

interface FileListProps {
  courseId: string;
}

export function FileList({ courseId }: FileListProps) {
  const [files, setFiles] = useState<IngestedFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await ingestionApi.files(courseId);
      setFiles(data);
    } catch (err) {
      console.error("Failed to fetch files:", err);
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleDelete = async (filename: string) => {
    if (deletingFile) return;
    try {
      setDeletingFile(filename);
      await ingestionApi.deleteFile(courseId, filename);
      setFiles((prev) => prev.filter((f) => f.filename !== filename));
    } catch (err) {
      console.error("Failed to delete file:", err);
    } finally {
      setDeletingFile(null);
    }
  };

  // ── Loading ─────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="h-[44px] rounded-[var(--radius-lg)] bg-[rgba(239,243,244,0.04)] animate-pulse"
          />
        ))}
      </div>
    );
  }

  // ── Empty ───────────────────────────────────────────────────────────────

  if (files.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-[13px] text-[var(--color-text-dim)]">
          No files indexed yet
        </p>
        <p className="text-[11px] text-[var(--color-text-dim)] mt-1">
          Upload documents or sync from Classroom
        </p>
      </div>
    );
  }

  // ── Table ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-1">
      {files.map((file) => (
        <div
          key={file.filename}
          className="
            flex items-center gap-3
            px-3 py-2.5
            rounded-[var(--radius-lg)]
            hover:bg-[rgba(239,243,244,0.04)]
            transition-colors duration-100
            group
          "
        >
          {/* File icon */}
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[var(--color-text-dim)] flex-shrink-0"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>

          {/* Filename + metadata */}
          <div className="flex-1 min-w-0">
            <p className="text-[13px] text-[var(--color-text-main)] truncate">
              {file.filename}
            </p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[10px] text-[var(--color-text-dim)]">
                {file.chunk_count} chunk{file.chunk_count !== 1 ? "s" : ""}
              </span>
              <span className="text-[10px] text-[var(--color-text-dim)]">
                · {file.source}
              </span>
            </div>
          </div>

          {/* Delete button */}
          <button
            onClick={() => handleDelete(file.filename)}
            disabled={deletingFile === file.filename}
            className="
              opacity-0 group-hover:opacity-100
              w-7 h-7 rounded-full
              flex items-center justify-center
              text-[var(--color-text-dim)]
              hover:bg-[var(--color-danger-dim)]
              hover:text-[var(--color-danger)]
              transition-all duration-150
              disabled:opacity-50
            "
            aria-label={`Delete ${file.filename}`}
          >
            {deletingFile === file.filename ? (
              <div className="w-3 h-3 border-2 border-[var(--color-text-dim)] border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              </svg>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}

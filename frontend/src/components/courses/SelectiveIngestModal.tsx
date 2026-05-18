"use client";

// ─────────────────────────────────────────────────────────────────────────────
// SelectiveIngestModal
//
// A modal that lets the user choose which specific Google Classroom items
// (assignments, materials, announcements) to ingest into the RAG index,
// instead of ingesting the entire course at once.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState, useCallback } from "react";
import { ingestionApi } from "@/lib/api";
import type { ClassroomItem } from "@/lib/types";
import {
  X,
  ClipboardList,
  BookOpen,
  Megaphone,
  ExternalLink,
  CheckSquare,
  Square,
  Zap,
  Loader2,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

// ─── Type Icons ───────────────────────────────────────────────────────────────
function TypeIcon({ type }: { type: ClassroomItem["type"] }) {
  const cls = "flex-shrink-0";
  if (type === "assignment") return <ClipboardList size={14} className={cls} />;
  if (type === "material") return <BookOpen size={14} className={cls} />;
  return <Megaphone size={14} className={cls} />;
}

// ─── Type Badge ───────────────────────────────────────────────────────────────
const TYPE_COLORS: Record<ClassroomItem["type"], string> = {
  assignment: "bg-[rgba(29,155,240,0.15)] text-[#1d9bf0]",
  material: "bg-[rgba(0,186,124,0.15)] text-[#00ba7c]",
  announcement: "bg-[rgba(255,212,0,0.15)] text-[#ffd400]",
};

function TypeBadge({ type }: { type: ClassroomItem["type"] }) {
  return (
    <span
      className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full capitalize ${TYPE_COLORS[type]}`}
    >
      {type}
    </span>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────
interface SelectiveIngestModalProps {
  courseId: string;
  isOpen: boolean;
  onClose: () => void;
  onStartIngestion: (selectedItemIds: string[]) => void;
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function SelectiveIngestModal({
  courseId,
  isOpen,
  onClose,
  onStartIngestion,
}: SelectiveIngestModalProps) {
  const [items, setItems] = useState<ClassroomItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | ClassroomItem["type"]>("all");

  // ── Fetch Classroom items ─────────────────────────────────────────────────
  const fetchItems = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await ingestionApi.courseworkFiles(courseId);
      setItems(data);
      // Default: select all
      setSelected(new Set(data.map((i) => i.item_id)));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to load classroom materials."
      );
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    if (isOpen) {
      fetchItems();
    } else {
      // Reset on close
      setItems([]);
      setSelected(new Set());
      setError(null);
      setFilter("all");
    }
  }, [isOpen, fetchItems]);

  // ── Close on Escape ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // ── Filtering & Selection ─────────────────────────────────────────────────
  const filteredItems =
    filter === "all" ? items : items.filter((i) => i.type === filter);

  const allFilteredSelected = filteredItems.every((i) =>
    selected.has(i.item_id)
  );

  const toggleItem = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allFilteredSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        filteredItems.forEach((i) => next.delete(i.item_id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        filteredItems.forEach((i) => next.add(i.item_id));
        return next;
      });
    }
  };

  const handleIngest = () => {
    if (selected.size === 0) return;
    onStartIngestion(Array.from(selected));
    onClose();
  };

  const counts = items.reduce(
    (acc, i) => {
      acc[i.type] = (acc[i.type] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const filters: Array<{ key: "all" | ClassroomItem["type"]; label: string }> =
    [
      { key: "all", label: `All (${items.length})` },
      { key: "assignment", label: `Assignments (${counts.assignment ?? 0})` },
      { key: "material", label: `Materials (${counts.material ?? 0})` },
      {
        key: "announcement",
        label: `Announcements (${counts.announcement ?? 0})`,
      },
    ];

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-[600px] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-[0_24px_80px_rgba(0,0,0,0.7)] overflow-hidden pointer-events-auto"
          style={{ maxHeight: "80vh", display: "flex", flexDirection: "column" }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* ── Header ──────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
            <div>
              <h2 className="text-[15px] font-semibold text-[var(--color-text-main)]">
                Select Items to Index
              </h2>
              <p className="text-[12px] text-[var(--color-text-dim)] mt-0.5">
                Choose which Google Classroom items to add to the RAG index.
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-full text-[var(--color-text-dim)] hover:text-[var(--color-text-main)] hover:bg-[rgba(239,243,244,0.08)] transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          {/* ── Filter tabs ─────────────────────────────────────────────── */}
          {!loading && !error && items.length > 0 && (
            <div className="flex items-center gap-1 px-5 py-3 border-b border-[var(--color-border)] overflow-x-auto">
              {filters.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={`px-3 py-1.5 rounded-full text-[11px] font-medium whitespace-nowrap transition-all duration-150 ${
                    filter === key
                      ? "bg-[rgba(239,243,244,0.12)] text-[var(--color-text-main)]"
                      : "text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* ── Content ─────────────────────────────────────────────────── */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Loader2
                  size={24}
                  className="text-[var(--color-text-dim)] animate-spin"
                />
                <p className="text-[13px] text-[var(--color-text-dim)]">
                  Loading Classroom materials…
                </p>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
                <AlertTriangle
                  size={24}
                  className="text-[var(--color-warning)]"
                />
                <p className="text-[13px] text-[var(--color-text-muted)]">
                  {error}
                </p>
                <button
                  onClick={fetchItems}
                  className="flex items-center gap-1.5 text-[12px] text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] mt-1"
                >
                  <RefreshCw size={12} /> Try again
                </button>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-2">
                <p className="text-[13px] text-[var(--color-text-dim)]">
                  No items found.
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {/* Select all row */}
                <div className="flex items-center gap-3 px-3 py-2 rounded-lg mb-2">
                  <button
                    onClick={toggleAll}
                    className="text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] transition-colors"
                    aria-label={
                      allFilteredSelected ? "Deselect all" : "Select all"
                    }
                  >
                    {allFilteredSelected ? (
                      <CheckSquare size={15} className="text-[#1d9bf0]" />
                    ) : (
                      <Square size={15} />
                    )}
                  </button>
                  <span className="text-[12px] text-[var(--color-text-dim)]">
                    {allFilteredSelected
                      ? "Deselect all"
                      : `Select all ${filteredItems.length}`}
                  </span>
                  <span className="ml-auto text-[11px] text-[var(--color-text-dim)]">
                    {selected.size} of {items.length} selected
                  </span>
                </div>

                {/* Item rows */}
                {filteredItems.map((item) => {
                  const isSelected = selected.has(item.item_id);
                  return (
                    <div
                      key={item.item_id}
                      onClick={() => toggleItem(item.item_id)}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-100 ${
                        isSelected
                          ? "bg-[rgba(29,155,240,0.06)] border border-[rgba(29,155,240,0.15)]"
                          : "hover:bg-[rgba(239,243,244,0.04)] border border-transparent"
                      }`}
                    >
                      {/* Checkbox */}
                      <div className="flex-shrink-0">
                        {isSelected ? (
                          <CheckSquare size={15} className="text-[#1d9bf0]" />
                        ) : (
                          <Square
                            size={15}
                            className="text-[var(--color-text-dim)]"
                          />
                        )}
                      </div>

                      {/* Type icon */}
                      <div className="text-[var(--color-text-dim)]">
                        <TypeIcon type={item.type} />
                      </div>

                      {/* Title + meta */}
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-[13px] truncate ${
                            isSelected
                              ? "text-[var(--color-text-main)]"
                              : "text-[var(--color-text-muted)]"
                          }`}
                        >
                          {item.title}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <TypeBadge type={item.type} />
                          {item.attachment_count > 0 && (
                            <span className="text-[10px] text-[var(--color-text-dim)]">
                              {item.attachment_count} attachment
                              {item.attachment_count !== 1 ? "s" : ""}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* External link */}
                      {item.alternateLink && (
                        <a
                          href={item.alternateLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex-shrink-0 text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] transition-colors"
                          aria-label="Open in Classroom"
                        >
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Footer ──────────────────────────────────────────────────── */}
          {!loading && !error && items.length > 0 && (
            <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-[var(--color-border)]">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-full text-[13px] text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] hover:bg-[rgba(239,243,244,0.06)] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleIngest}
                disabled={selected.size === 0}
                className="flex items-center gap-2 px-5 py-2 rounded-full bg-[var(--color-primary)] text-black text-[13px] font-semibold hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Zap size={13} />
                Index {selected.size} item{selected.size !== 1 ? "s" : ""}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

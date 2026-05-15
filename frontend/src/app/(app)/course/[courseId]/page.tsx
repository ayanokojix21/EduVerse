"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Course Detail Page — /course/[courseId]
//
// Full-page replacement for the old CourseDrawer. Sections:
//   1. Header — course name, source badge, actions (Chat, Delete)
//   2. Ingestion Status — progress bar, status, action buttons
//   3. Tabs — Files | Assignments | Sessions
// ─────────────────────────────────────────────────────────────────────────────

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  MessageSquare,
  Upload,
  RefreshCw,
  Trash2,
  Database,
  MoreVertical,
  FileText,
  ExternalLink,
  Clock,
  Zap,
  ClipboardList,
  BookOpen,
  Megaphone,
  Paperclip,
  Play,
  Link2,
} from "lucide-react";
import { coursesApi, ingestionApi, sessionsApi } from "@/lib/api";
import type {
  UnifiedCourse,
  Coursework,
  CourseworkMaterial,
  IngestedFile,
  IngestionStatusValue,
  ChatSession,
} from "@/lib/types";
import { SourceBadge, IngestionDot } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

type Tab = "files" | "assignments" | "sessions";

const ACCEPTED_TYPES = ".pdf,.txt,.md,.docx";
const MAX_FILE_SIZE = 100 * 1024 * 1024;

export default function CourseDetailPage() {
  const params = useParams<{ courseId: string }>();
  const router = useRouter();
  const courseId = params.courseId;

  // ── Data state ───────────────────────────────────────────────────────────
  const [course, setCourse] = useState<UnifiedCourse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("files");

  // Files
  const [files, setFiles] = useState<IngestedFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  // Ingestion
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatusValue>("none");
  const [fileCount, setFileCount] = useState(0);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  // Upload
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Assignments
  const [coursework, setCoursework] = useState<Coursework[]>([]);
  const [courseworkLoading, setCourseworkLoading] = useState(false);
  const [courseworkLoaded, setCourseworkLoaded] = useState(false);

  // Sessions
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsLoaded, setSessionsLoaded] = useState(false);

  // UI
  const [showMenu, setShowMenu] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load course ──────────────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);
        const all = await coursesApi.list();
        const found = all.find((c) => c.id === courseId);
        if (found) setCourse(found);
        else router.replace("/dashboard");
      } catch {
        router.replace("/dashboard");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [courseId, router]);

  // ── Load files ───────────────────────────────────────────────────────────
  const fetchFiles = useCallback(async () => {
    try {
      setFilesLoading(true);
      const data = await ingestionApi.files(courseId);
      setFiles(data);
    } catch {
      console.error("Failed to fetch files");
    } finally {
      setFilesLoading(false);
    }
  }, [courseId]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  // ── Poll ingestion status ────────────────────────────────────────────────
  const pollIngestion = useCallback(async () => {
    try {
      const data = await ingestionApi.status(courseId);
      setIngestionStatus(data.status);
      setFileCount(data.current_file_count);
      setIngestionError(data.error ?? null);
      if (data.status === "completed" || data.status === "failed" || data.status === "none") {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        if (data.status === "completed") fetchFiles();
      }
    } catch { /* ignore */ }
  }, [courseId, fetchFiles]);

  useEffect(() => {
    pollIngestion();
    pollRef.current = setInterval(pollIngestion, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [pollIngestion]);

  // ── Tab data loaders ─────────────────────────────────────────────────────
  const loadCoursework = useCallback(async () => {
    if (courseworkLoaded) return;
    try {
      setCourseworkLoading(true);
      const data = await coursesApi.coursework(courseId);
      setCoursework(data);
      setCourseworkLoaded(true);
    } catch { console.error("Failed to load coursework"); }
    finally { setCourseworkLoading(false); }
  }, [courseId, courseworkLoaded]);

  const loadSessions = useCallback(async () => {
    if (sessionsLoaded) return;
    try {
      setSessionsLoading(true);
      const data = await sessionsApi.list(courseId);
      setSessions(data);
      setSessionsLoaded(true);
    } catch { console.error("Failed to load sessions"); }
    finally { setSessionsLoading(false); }
  }, [courseId, sessionsLoaded]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    if (tab === "assignments") loadCoursework();
    if (tab === "sessions") loadSessions();
  };

  // ── Actions ──────────────────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    if (file.size > MAX_FILE_SIZE) { setUploadError("File exceeds 100 MB"); return; }
    try {
      setIsUploading(true); setUploadError(null);
      const fd = new FormData();
      fd.append("file", file);
      fd.append("course_id", courseId);
      await ingestionApi.upload(fd);
      await ingestionApi.trigger(courseId);
      pollRef.current = setInterval(pollIngestion, 3000);
      fetchFiles();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally { setIsUploading(false); }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleUpload(f);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleUpload(f);
  };

  const handleIndex = async () => {
    try { setIsIndexing(true); await ingestionApi.trigger(courseId); pollRef.current = setInterval(pollIngestion, 3000); }
    catch { console.error("Index failed"); } finally { setIsIndexing(false); }
  };

  const handleSync = async () => {
    try { setIsSyncing(true); await ingestionApi.sync(courseId); pollRef.current = setInterval(pollIngestion, 3000); }
    catch { console.error("Sync failed"); } finally { setIsSyncing(false); }
  };

  const handleClearIndex = async () => {
    if (!confirm("This will wipe ALL indexed data for this course. Continue?")) return;
    try { setIsClearing(true); await ingestionApi.deleteIndex(courseId); setFiles([]); setFileCount(0); setIngestionStatus("none"); }
    catch { console.error("Clear failed"); } finally { setIsClearing(false); }
  };

  const handleDeleteFile = async (filename: string) => {
    if (deletingFile) return;
    try { setDeletingFile(filename); await ingestionApi.deleteFile(courseId, filename); setFiles((p) => p.filter((f) => f.filename !== filename)); }
    catch { console.error("Delete failed"); } finally { setDeletingFile(null); }
  };

  const handleDeleteCourse = async () => {
    if (!confirm("Delete this course and all indexed data?")) return;
    try { setIsDeleting(true); await coursesApi.delete(courseId); router.push("/dashboard"); }
    catch { console.error("Delete failed"); } finally { setIsDeleting(false); }
  };

  // ── Loading state ────────────────────────────────────────────────────────
  if (isLoading || !course) {
    return (
      <div className="max-w-[900px] mx-auto px-6 py-10 space-y-6">
        <div className="w-40 h-6 bg-[rgba(239,243,244,0.06)] rounded animate-pulse" />
        <div className="h-[80px] rounded-xl bg-[rgba(239,243,244,0.04)] animate-pulse" />
        <div className="h-[300px] rounded-xl bg-[rgba(239,243,244,0.04)] animate-pulse" />
      </div>
    );
  }

  const isProcessing = ingestionStatus === "processing" || ingestionStatus === "pending";

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="max-w-[900px] mx-auto px-6 py-8 space-y-6 animate-[fade-up_0.3s_ease-out_both]">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-[13px] text-[var(--color-text-dim)] hover:text-[var(--color-text-muted)] transition-colors mb-3">
            <ArrowLeft size={14} /> Dashboard
          </Link>
          <h1 className="text-[24px] font-bold text-[var(--color-text-main)] truncate">{course.name}</h1>
          <div className="flex items-center gap-3 mt-2">
            <SourceBadge source={course.source} />
            {course.description && <span className="text-[13px] text-[var(--color-text-muted)] truncate">{course.description}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 pt-8">
          <Link href={`/chat/${courseId}`} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--color-primary)] text-black text-[13px] font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
            <MessageSquare size={14} /> Open Chat
          </Link>
          <div className="relative">
            <button onClick={() => setShowMenu((p) => !p)} className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--color-text-dim)] hover:bg-[rgba(239,243,244,0.08)] transition-colors" aria-label="More options">
              <MoreVertical size={16} />
            </button>
            {showMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 w-48 bg-[var(--color-panel)] border border-[var(--color-border)] rounded-xl overflow-hidden shadow-[0_4px_24px_rgba(0,0,0,0.5)]">
                  <button onClick={() => { setShowMenu(false); handleDeleteCourse(); }} disabled={isDeleting} className="w-full flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-[var(--color-danger)] hover:bg-[var(--color-danger-dim)] transition-colors">
                    <Trash2 size={14} /> Delete Course
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Ingestion Status Banner ─────────────────────────────────────── */}
      <div className="border border-[var(--color-border)] rounded-xl p-4 animate-[fade-up_0.35s_ease-out_both]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <IngestionDot status={ingestionStatus} />
            <span className="text-[13px] font-medium text-[var(--color-text-main)] capitalize">
              {ingestionStatus === "none" ? "Not indexed" : ingestionStatus === "processing" ? "Indexing…" : ingestionStatus}
            </span>
            {ingestionError && ingestionStatus === "failed" && (
              <span className="text-[11px] text-[var(--color-danger)] truncate max-w-[200px]">{ingestionError}</span>
            )}
          </div>
          <span className="text-[12px] text-[var(--color-text-dim)]">
            {fileCount} file{fileCount !== 1 ? "s" : ""} indexed
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-1 w-full bg-[rgba(239,243,244,0.06)] rounded-full overflow-hidden mb-3">
          <div className={`h-full rounded-full transition-all duration-500 ${isProcessing ? "animate-[progress-indeterminate_1.5s_ease-in-out_infinite]" : ""}`}
            style={{
              backgroundColor: ingestionStatus === "completed" ? "#00BA7C" : ingestionStatus === "failed" ? "#F4212E" : isProcessing ? "#FFD400" : "#536471",
              width: ingestionStatus === "completed" ? "100%" : isProcessing ? "60%" : ingestionStatus === "none" ? "0%" : "100%",
            }}
          />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="ghost" size="sm" onClick={handleIndex} loading={isIndexing} leftIcon={<Zap size={13} />}>
            Index Files
          </Button>
          {course.source === "classroom" && (
            <Button variant="ghost" size="sm" onClick={handleSync} loading={isSyncing} className="text-[#1d9bf0] border-[#1d9bf0]/20 hover:bg-[#1d9bf0]/10" leftIcon={<RefreshCw size={13} />}>
              Sync Classroom
            </Button>
          )}
          {fileCount > 0 && (
            <Button variant="ghost" size="sm" onClick={handleClearIndex} loading={isClearing} className="text-[var(--color-danger)] border-[var(--color-danger)]/20 hover:bg-[var(--color-danger-dim)]" leftIcon={<Trash2 size={13} />}>
              Clear Index
            </Button>
          )}
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="border-b border-[var(--color-border)] flex animate-[fade-up_0.4s_ease-out_both]">
        {(["files", "assignments", "sessions"] as Tab[]).map((tab) => (
          <button key={tab} onClick={() => handleTabChange(tab)}
            className={`flex-1 py-3 text-[13px] font-medium capitalize transition-colors border-b-2 ${
              activeTab === tab ? "text-[var(--color-text-main)] border-[var(--color-text-main)]" : "text-[var(--color-text-dim)] border-transparent hover:text-[var(--color-text-muted)]"
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {/* ── Tab Content ─────────────────────────────────────────────────── */}
      <div className="min-h-[300px] animate-[fade-in_0.2s_ease-out_both]">
        {activeTab === "files" && (
          <div className="space-y-4">
            {/* Upload zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
                isDragging ? "border-[#1d9bf0] bg-[rgba(29,155,240,0.05)]" : "border-[var(--color-border)] hover:border-[var(--color-border-focus)] hover:bg-[rgba(239,243,244,0.02)]"
              }`}
            >
              {isUploading ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-[var(--color-text-dim)] border-t-transparent rounded-full animate-spin" />
                  <span className="text-[13px] text-[var(--color-text-muted)]">Uploading…</span>
                </div>
              ) : (
                <>
                  <Upload size={24} className="mx-auto mb-2 text-[var(--color-text-dim)]" />
                  <p className="text-[13px] text-[var(--color-text-muted)]">Click to upload or drag & drop</p>
                  <p className="text-[11px] text-[var(--color-text-dim)] mt-1">PDF, TXT, MD, DOCX — max 100 MB</p>
                </>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept={ACCEPTED_TYPES} onChange={handleFileSelect} className="hidden" />
            {uploadError && <p className="text-[11px] text-[var(--color-danger)]">{uploadError}</p>}

            {/* File list */}
            {filesLoading ? (
              <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-[52px] rounded-lg bg-[rgba(239,243,244,0.04)] animate-pulse" />)}</div>
            ) : files.length === 0 ? (
              <div className="text-center py-10">
                <Database size={32} className="mx-auto mb-3 text-[var(--color-text-dim)] opacity-50" />
                <p className="text-[13px] text-[var(--color-text-dim)]">No files indexed yet</p>
                <p className="text-[11px] text-[var(--color-text-dim)] mt-1">Upload documents or sync from Classroom</p>
              </div>
            ) : (
              <div className="space-y-1">
                {files.map((file) => (
                  <div key={file.filename} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[rgba(239,243,244,0.04)] transition-colors group">
                    <FileText size={16} className="text-[var(--color-text-dim)] flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] text-[var(--color-text-main)] truncate">{file.filename}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-[var(--color-text-dim)]">{file.chunk_count} chunk{file.chunk_count !== 1 ? "s" : ""}</span>
                        <span className="text-[10px] text-[var(--color-text-dim)]">· {file.source}</span>
                      </div>
                    </div>
                    <button onClick={() => handleDeleteFile(file.filename)} disabled={deletingFile === file.filename}
                      className="opacity-0 group-hover:opacity-100 w-7 h-7 rounded-full flex items-center justify-center text-[var(--color-text-dim)] hover:bg-[var(--color-danger-dim)] hover:text-[var(--color-danger)] transition-all disabled:opacity-50"
                      aria-label={`Delete ${file.filename}`}>
                      {deletingFile === file.filename ? <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <Trash2 size={13} />}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "assignments" && <CourseworkSection course={course} coursework={coursework} loading={courseworkLoading} />}

        {activeTab === "sessions" && (
          <div>
            <div className="mb-4">
              <Link href={`/chat/${courseId}`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--color-border)] text-[13px] font-medium text-[var(--color-text-main)] hover:bg-[rgba(239,243,244,0.06)] transition-colors">
                <MessageSquare size={14} /> Start New Chat
              </Link>
            </div>
            {sessionsLoading ? (
              <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-[56px] rounded-lg bg-[rgba(239,243,244,0.04)] animate-pulse" />)}</div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-10">
                <MessageSquare size={32} className="mx-auto mb-3 text-[var(--color-text-dim)] opacity-50" />
                <p className="text-[13px] text-[var(--color-text-dim)]">No chat sessions yet</p>
                <p className="text-[11px] text-[var(--color-text-dim)] mt-1">Start a chat to begin learning</p>
              </div>
            ) : (
              <div className="space-y-1">
                {sessions.map((s) => (
                  <Link key={s.session_id} href={`/chat/${courseId}?session=${s.session_id}`}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-[rgba(239,243,244,0.04)] transition-colors group">
                    <MessageSquare size={16} className="text-[var(--color-text-dim)] flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] text-[var(--color-text-main)] truncate">{s.title || "Untitled session"}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Clock size={10} className="text-[var(--color-text-dim)]" />
                        <span className="text-[10px] text-[var(--color-text-dim)]">{new Date(s.created_at).toLocaleDateString()}</span>
                        {s.message_count != null && <span className="text-[10px] text-[var(--color-text-dim)]">· {s.message_count} messages</span>}
                      </div>
                    </div>
                    <ArrowLeft size={14} className="rotate-180 text-[var(--color-text-dim)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Sub-Components ─────────────────────────────────────────────────────────

function CourseworkSection({ course, coursework, loading }: { course: UnifiedCourse; coursework: Coursework[]; loading: boolean }) {
  const [filter, setFilter] = useState<"all" | "assignment" | "material" | "announcement">("all");

  const filtered = coursework.filter((cw) => filter === "all" || cw.type === filter);

  const typeConfig = {
    assignment: { color: "text-[#1d9bf0]", bg: "bg-[#1d9bf0]/10", border: "border-[#1d9bf0]/20", label: "Assignment", icon: ClipboardList },
    material: { color: "text-[#a78bfa]", bg: "bg-[#a78bfa]/10", border: "border-[#a78bfa]/20", label: "Material", icon: BookOpen },
    announcement: { color: "text-[#fbbf24]", bg: "bg-[#fbbf24]/10", border: "border-[#fbbf24]/20", label: "Announcement", icon: Megaphone },
  };

  const getDueDateStr = (dueDate?: { year?: number; month?: number; day?: number } | null) => {
    if (!dueDate || !dueDate.year || !dueDate.month || !dueDate.day) return null;
    return new Date(dueDate.year, dueDate.month - 1, dueDate.day).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  if (loading) {
    return <div className="space-y-2">{[...Array(4)].map((_, i) => <div key={i} className="h-[120px] rounded-xl bg-[rgba(239,243,244,0.04)] animate-pulse" />)}</div>;
  }

  if (coursework.length === 0) {
    return (
      <div className="text-center py-10">
        <FileText size={32} className="mx-auto mb-3 text-[var(--color-text-dim)] opacity-50" />
        <p className="text-[13px] text-[var(--color-text-dim)]">{course.source === "classroom" ? "No coursework found" : "Coursework is only available for Classroom courses"}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-[fade-in_0.2s_ease-out_both]">
      {/* Filters */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {(["all", "assignment", "material", "announcement"] as const).map((f) => {
          const count = f === "all" ? coursework.length : coursework.filter(cw => cw.type === f).length;
          if (f !== "all" && count === 0) return null;
          return (
            <button key={f} onClick={() => setFilter(f)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors border whitespace-nowrap ${
                filter === f
                  ? "bg-[rgba(255,255,255,0.1)] border-[rgba(255,255,255,0.1)] text-[var(--color-text-main)]"
                  : "bg-transparent border-[var(--color-border)] text-[var(--color-text-dim)] hover:border-[var(--color-border-focus)] hover:text-[var(--color-text-muted)]"
              }`}>
              <span className="capitalize">{f}s</span>
              <span className={`px-1.5 rounded-full text-[10px] ${filter === f ? "bg-white/20 text-white" : "bg-[rgba(255,255,255,0.08)] text-[var(--color-text-dim)]"}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <div className="text-center py-10 text-[13px] text-[var(--color-text-dim)]">No {filter}s found.</div>
      ) : (
        <div className="space-y-4">
          {filtered.map((cw) => {
            const config = cw.type ? typeConfig[cw.type as keyof typeof typeConfig] : null;
            const Icon = config?.icon || FileText;
            const dueStr = getDueDateStr(cw.dueDate);
            const createdStr = cw.creationTime ? new Date(cw.creationTime).toLocaleDateString() : null;

            return (
              <div key={cw.id} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-panel)] overflow-hidden hover:border-[var(--color-border-focus)] transition-colors">
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className={`mt-0.5 p-2 rounded-lg ${config?.bg || "bg-[rgba(239,243,244,0.06)]"}`}>
                        <Icon size={16} className={config?.color || "text-[var(--color-text-dim)]"} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {config && <span className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-md border ${config.bg} ${config.color} ${config.border}`}>{config.label}</span>}
                          {dueStr && <span className="text-[11px] font-medium text-[var(--color-warning)] bg-[var(--color-warning-dim)] px-2 py-0.5 rounded-md border border-[var(--color-warning)]/20">Due: {dueStr}</span>}
                          {createdStr && <span className="text-[11px] text-[var(--color-text-dim)]">Posted {createdStr}</span>}
                        </div>
                        <a href={cw.alternateLink} target="_blank" rel="noopener noreferrer" className="text-[15px] font-semibold text-[var(--color-text-main)] hover:text-[#1d9bf0] transition-colors truncate block">
                          {cw.title}
                        </a>
                        {cw.description && <p className="text-[13px] text-[var(--color-text-muted)] line-clamp-3 mt-1.5 whitespace-pre-wrap">{cw.description}</p>}
                      </div>
                    </div>
                    {cw.alternateLink && (
                      <a href={cw.alternateLink} target="_blank" rel="noopener noreferrer" className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-[var(--color-text-dim)] hover:text-[#1d9bf0] hover:bg-[#1d9bf0]/10 transition-colors" aria-label="Open in Classroom">
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </div>

                {/* Attachments */}
                {cw.materials && cw.materials.length > 0 && (
                  <div className="border-t border-[var(--color-border)] bg-[rgba(239,243,244,0.02)] p-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {cw.materials.map((m, idx) => {
                        let icon = <Paperclip size={14} />;
                        let title = "Attachment";
                        let url = "#";
                        
                        if (m.driveFile?.driveFile) {
                          title = m.driveFile.driveFile.title || title;
                          url = m.driveFile.driveFile.alternateLink || url;
                          icon = <FileText size={14} />;
                        } else if (m.youtubeVideo) {
                          title = m.youtubeVideo.title || title;
                          url = m.youtubeVideo.alternateLink || url;
                          icon = <Play size={14} className="text-[#f4212e]" />;
                        } else if (m.link) {
                          title = m.link.title || title;
                          url = m.link.url || url;
                          icon = <Link2 size={14} />;
                        }

                        return (
                          <a key={idx} href={url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2.5 p-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-text-dim)] transition-colors group">
                            <div className="w-7 h-7 rounded bg-[rgba(239,243,244,0.06)] flex items-center justify-center text-[var(--color-text-dim)] group-hover:text-[var(--color-text-main)] transition-colors">
                              {icon}
                            </div>
                            <span className="text-[12px] font-medium text-[var(--color-text-main)] truncate group-hover:text-[#1d9bf0] transition-colors">{title}</span>
                          </a>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

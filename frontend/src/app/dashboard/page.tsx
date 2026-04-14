'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  BookOpen, LogOut, MessageSquare, RefreshCw,
  AlertCircle, Loader2, Trash2, FileText, ChevronDown, ListTree
} from 'lucide-react';
import { signOut, useSession } from 'next-auth/react';
import Image from 'next/image';

import Spinner from '@/components/Spinner';
import { api } from '@/lib/api';
import { useToast } from '@/components/Toast';
import type { Course, Profile } from '@/types';
import styles from './dashboard.module.css';

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const { showToast } = useToast();

  const [courses, setCourses] = useState<Course[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState<Record<string, boolean>>({});
  const [courseFiles, setCourseFiles] = useState<Record<string, any[]>>({});
  const [showIndexManager, setShowIndexManager] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace('/');
    } else if (status === 'authenticated') {
      fetchDashboardData();
    }
  }, [status, router]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [coursesData, profileData] = await Promise.all([
        api.courses.list(),
        api.profile.get(),
      ]);
      setCourses(coursesData);
      setProfile(profileData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const pollIngestionStatus = async (courseId: string, idx: number) => {
    const key = `${courseId}-${idx}`;
    const poll = async () => {
      try {
        const statusData = await api.ingestion.getStatus(courseId);
        if (statusData.status === 'completed') {
          setIngesting(prev => ({ ...prev, [key]: false }));
          showToast(`Ingestion complete: ${courses.find(c => c.id === courseId)?.name}`, 'success');
          await fetchDashboardData();
          return true;
        } else if (statusData.status === 'failed') {
          setIngesting(prev => ({ ...prev, [key]: false }));
          showToast(`Ingestion failed: ${statusData.error || 'Unknown error'}`, 'error');
          return true;
        }
        return false;
      } catch (err) {
        console.error('Polling error:', err);
        return false;
      }
    };
    const interval = setInterval(async () => {
      const shouldStop = await poll();
      if (shouldStop) clearInterval(interval);
    }, 3000);
  };

  const handleIngest = async (courseId: string, idx: number) => {
    const key = `${courseId}-${idx}`;
    try {
      setIngesting(prev => ({ ...prev, [key]: true }));
      const response = await api.ingestion.trigger(courseId, true);
      if (response.status === 'accepted') {
        showToast('Ingestion started in background...', 'info');
        pollIngestionStatus(courseId, idx);
      } else {
        showToast('Ingestion complete!', 'success');
        setIngesting(prev => ({ ...prev, [key]: false }));
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to start ingestion', 'error');
      setIngesting(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleDeleteIndex = async (courseId: string, idx: number) => {
    const key = `${courseId}-${idx}`;
    if (!confirm('Wipe the AI index for this course? All learned materials will be removed.')) return;
    try {
      setIngesting(prev => ({ ...prev, [key]: true }));
      const result = await api.ingestion.deleteIndex(courseId);
      if (result.success) {
        showToast('Index wiped successfully.', 'success');
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to wipe index', 'error');
    } finally {
      setIngesting(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleDeleteFile = async (courseId: string, filename: string, idx: number) => {
    const key = `${courseId}-${idx}`;
    if (!confirm(`Delete "${filename}" from the AI index?`)) return;
    try {
      setIngesting(prev => ({ ...prev, [key]: true }));
      const result = await api.ingestion.deleteFile(courseId, filename);
      if (result.success) {
        showToast(`"${filename}" removed.`, 'success');
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to delete file', 'error');
    } finally {
      setIngesting(prev => ({ ...prev, [key]: false }));
    }
  };

  const fetchCourseFiles = async (courseId: string) => {
    try {
      const files = await api.ingestion.listFiles(courseId);
      setCourseFiles(prev => ({ ...prev, [courseId]: files }));
    } catch (err) {
      console.error('Failed to fetch course files:', err);
    }
  };

  const toggleIndexManager = (courseId: string, idx: number) => {
    const key = `${courseId}-${idx}`;
    const next = !showIndexManager[key];
    setShowIndexManager(prev => ({ ...prev, [key]: next }));
    if (next) fetchCourseFiles(courseId);
  };

  if (status === 'loading' || loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <AlertCircle size={40} style={{ color: '#e5484d' }} />
        <h2>Failed to load dashboard</h2>
        <p>{error}</p>
        <button className="btn btn-primary" onClick={fetchDashboardData}>Try Again</button>
      </div>
    );
  }


  return (
    <div className={styles.root}>
      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.logoRow}>
          <div className={styles.logoIcon}>
            <BookOpen size={14} strokeWidth={2.5} />
          </div>
          <span className={styles.logoText}>EduVerse</span>
        </div>

        <div className={styles.headerRight}>
          <div className={styles.userInfo}>
            {session?.user?.image ? (
              <Image
                src={session.user.image}
                alt="Avatar"
                width={28}
                height={28}
                className={styles.avatar}
              />
            ) : (
              <div className={styles.avatarFallback}>
                {session?.user?.name?.[0] || 'U'}
              </div>
            )}
            <span className={styles.userName}>{session?.user?.name}</span>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/' })}
            className="btn btn-ghost btn-icon"
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </header>

      {/* ── Main ── */}
      <main className={styles.main}>

        {/* Stats */}
        <div className={styles.statsRow}>
          <StatBox label="Enrolled Courses" value={courses.length} />
          <StatBox label="Tutoring Sessions" value={profile?.actual_session_count ?? profile?.session_count ?? 0} />
          <StatBox label="Documents Ingested" value={profile?.total_documents ?? 0} />
        </div>

        {/* Courses section */}
        <div className={styles.sectionHeader}>
          <h2>Your Courses</h2>
          <button className={styles.sectionLink} onClick={fetchDashboardData}>
            Sync from Classroom
          </button>
        </div>

        <div className={styles.courseGrid}>
            {courses.length === 0 ? (
              <div className={styles.emptyState}>
                <BookOpen size={28} style={{ color: '#3d3d3d' }} />
                <span>No Google Classroom courses found.</span>
              </div>
            ) : (
              courses.map((course, idx) => (
                <motion.div
                  key={`${course.id}-${idx}`}
                  className={styles.courseCard}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.04, duration: 0.3 }}
                >

                  {/* Card top */}
                  <div className={styles.courseCardTop} onClick={() => router.push(`/course/${course.id}`)} style={{ cursor: 'pointer' }}>
                    <h3 className={styles.courseTitle}>{course.name}</h3>
                    {course.section && (
                      <span className={styles.courseSection}>{course.section}</span>
                    )}
                  </div>

                  <div className={styles.courseCardMeta}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                       <span className={styles.metaBadge}>{course.assignment_count ?? 0} Assignments</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className={styles.courseActions}>
                    {course.is_ingested ? (
                      <>
                        <button
                          className={`btn ${styles.actionBtn} ${ingesting[`${course.id}-${idx}`] ? 'btn-loading' : ''}`}
                          onClick={() => handleIngest(course.id, idx)}
                          disabled={ingesting[`${course.id}-${idx}`]}
                          title="Re-sync materials"
                        >
                          {!ingesting[`${course.id}-${idx}`] && <RefreshCw size={13} />}
                          {ingesting[`${course.id}-${idx}`] ? 'Syncing' : 'Sync'}
                        </button>

                        <button
                          className={`${styles.actionBtn} ${styles.actionBtnIcon}`}
                          onClick={() => toggleIndexManager(course.id, idx)}
                          title="Manage indexed files"
                        >
                          <ChevronDown
                            size={13}
                            style={{
                              transform: showIndexManager[`${course.id}-${idx}`] ? 'rotate(180deg)' : 'none',
                              transition: 'transform 0.15s',
                            }}
                          />
                        </button>

                        <button
                          className={`${styles.actionBtn} ${styles.actionBtnIcon} ${styles.actionBtnDanger} ${ingesting[`${course.id}-${idx}`] ? 'btn-loading' : ''}`}
                          onClick={() => handleDeleteIndex(course.id, idx)}
                          disabled={ingesting[`${course.id}-${idx}`]}
                          title="Wipe index"
                        >
                          {!ingesting[`${course.id}-${idx}`] && <Trash2 size={13} />}
                        </button>
                      </>
                    ) : (
                      <button
                        className={styles.actionBtn}
                        onClick={() => handleIngest(course.id, idx)}
                        disabled={ingesting[`${course.id}-${idx}`]}
                      >
                        {ingesting[`${course.id}-${idx}`]
                          ? <Loader2 size={13} className="animate-spin" />
                          : <RefreshCw size={13} />
                        }
                        {ingesting[`${course.id}-${idx}`] ? 'Ingesting...' : 'Ingest Materials'}
                      </button>
                    )}

                    <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
                      <button
                        className={`${styles.actionBtn} ${styles.actionBtnSecondary}`}
                        onClick={() => router.push(`/course/${course.id}`)}
                      >
                        <ListTree size={13} />
                        Course Hub
                      </button>

                      <button
                        className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                        onClick={() => router.push(`/chat/${course.id}`)}
                      >
                        <MessageSquare size={13} />
                        Open Chat
                      </button>
                    </div>
                  </div>

                  {/* Index Manager Drawer */}
                  {showIndexManager[`${course.id}-${idx}`] && (
                    <div className={styles.indexDrawer}>
                      <div className={styles.indexDrawerHeader}>
                        <span className={styles.indexDrawerLabel}>Indexed Files</span>
                        <span className={styles.indexDrawerCount}>
                          {courseFiles[course.id]?.length ?? 0} documents
                        </span>
                      </div>
                      <div className={styles.indexFileList}>
                        {!courseFiles[course.id] || courseFiles[course.id].length === 0 ? (
                          <div className={styles.indexEmpty}>No files indexed yet.</div>
                        ) : (
                          courseFiles[course.id].map((file, fidx) => (
                            <div key={fidx} className={styles.indexFileRow}>
                              <FileText size={12} style={{ color: '#5e6ad2', flexShrink: 0 }} />
                              <span className={styles.indexFileName} title={file.filename}>
                                {file.filename}
                              </span>
                              <span className={styles.indexFileChunks}>{file.chunk_count} chk</span>
                              <button
                                className={styles.indexFileDelete}
                                onClick={() => handleDeleteFile(course.id, file.filename, idx)}
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              ))
            )}
          </div>
        </main>

    </div>
  );
}

function StatBox({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.statBox}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className="skeleton" style={{ width: 110, height: 24 }} />
        <div className="skeleton" style={{ width: 140, height: 24 }} />
      </header>
      <main className={styles.main}>
        <div className={styles.statsRow}>
          {[1, 2, 3].map(k => (
            <div key={k} className={`${styles.statBox} skeleton`} style={{ height: 72 }} />
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="skeleton" style={{ width: 180, height: 22 }} />
          <div className={styles.courseGrid}>
            {[1, 2, 3].map(k => (
              <div key={k} className={`${styles.courseCard} skeleton`} style={{ height: 180 }} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

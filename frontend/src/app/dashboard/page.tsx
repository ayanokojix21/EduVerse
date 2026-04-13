'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { BookOpen, LogOut, MessageSquare, RefreshCw, AlertCircle, Sparkles, Loader2, Trash2, FileText } from 'lucide-react';
import { signOut, useSession } from 'next-auth/react';
import Image from 'next/image';

import ThemeToggle from '@/components/ThemeToggle';
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
        api.profile.get()
      ]);
      setCourses(coursesData);
      setProfile(profileData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const pollIngestionStatus = async (courseId: string) => {
    const poll = async () => {
      try {
        const statusData = await api.ingestion.getStatus(courseId);
        
        if (statusData.status === 'completed') {
          setIngesting(prev => ({ ...prev, [courseId]: false }));
          showToast(`Ingestion complete: ${courses.find(c => c.id === courseId)?.name}`, 'success');
          await fetchDashboardData(); // Refresh page data
          return true; // Stop polling
        } else if (statusData.status === 'failed') {
          setIngesting(prev => ({ ...prev, [courseId]: false }));
          showToast(`Ingestion failed: ${statusData.error || 'Unknown error'}`, 'error');
          return true; // Stop polling
        }
        return false; // Keep polling
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

  const handleIngest = async (courseId: string) => {
    try {
      setIngesting(prev => ({ ...prev, [courseId]: true }));
      const response = await api.ingestion.trigger(courseId, true);
      
      if (response.status === 'accepted') {
        showToast('Ingestion started in background...', 'info');
        pollIngestionStatus(courseId);
      } else {
        // Fallback for sync responses if any
        showToast('Ingestion complete!', 'success');
        setIngesting(prev => ({ ...prev, [courseId]: false }));
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to start ingestion', 'error');
      setIngesting(prev => ({ ...prev, [courseId]: false }));
    }
  };

  const handleDeleteIndex = async (courseId: string) => {
    if (!confirm('Are you sure you want to completely wipe the AI index for this course? This will remove all learned materials.')) return;
    
    try {
      setIngesting(prev => ({ ...prev, [courseId]: true }));
      const result = await api.ingestion.deleteIndex(courseId);
      if (result.success) {
        showToast('Index wiped successfully.', 'success');
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to wipe index', 'error');
    } finally {
      setIngesting(prev => ({ ...prev, [courseId]: false }));
    }
  };

  const handleDeleteFile = async (courseId: string, filename: string) => {
    if (!confirm(`Delete "${filename}" from the AI index?`)) return;
    
    try {
      setIngesting(prev => ({ ...prev, [courseId]: true }));
      const result = await api.ingestion.deleteFile(courseId, filename);
      if (result.success) {
        showToast(`"${filename}" removed.`, 'success');
        await fetchDashboardData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to delete file', 'error');
    } finally {
      setIngesting(prev => ({ ...prev, [courseId]: false }));
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

  const toggleIndexManager = (courseId: string) => {
    const nextState = !showIndexManager[courseId];
    setShowIndexManager(prev => ({ ...prev, [courseId]: nextState }));
    if (nextState) {
      fetchCourseFiles(courseId);
    }
  };

  if (status === 'loading' || loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <AlertCircle size={48} className="text-error" />
        <h2>Failed to load dashboard</h2>
        <p>{error}</p>
        <button className="btn btn-primary" onClick={fetchDashboardData}>
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      {/* ── Background ── */}
      <div className="mesh-bg" aria-hidden style={{ opacity: 0.5 }} />

      {/* ── Header ── */}
      <header className={`${styles.header} glass-card`}>
        <div className={styles.logoRow}>
          <div className={styles.logoIcon}>
            <BookOpen size={20} />
          </div>
          <span className={`${styles.logoText} font-display`}>EduVerse</span>
        </div>

        <div className={styles.headerRight}>
          <ThemeToggle />
          <div className={styles.userInfo}>
            {session?.user?.image ? (
              <Image 
                src={session.user.image} 
                alt="Avatar" 
                width={32} 
                height={32} 
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
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <main className={styles.main}>
        
        {/* Left Column: Stats & Courses */}
        <div className={styles.leftColumn}>
          {/* Stats Row */}
          <div className={styles.statsRow}>
            <StatBox label="Enrolled Courses" value={courses.length} />
            <StatBox label="Tutoring Sessions" value={profile?.session_count || 0} />
            <StatBox label="Topics to Review" value={profile?.weak_topics?.length || 0} />
          </div>

          <div className={styles.sectionHeader}>
            <h2 className="font-display">Your Courses</h2>
          </div>

          {/* Course Grid */}
          <div className={styles.courseGrid}>
            {courses.length === 0 ? (
              <div className={styles.emptyState}>
                <BookOpen size={32} className="text-tertiary" />
                <p>No Google Classroom courses found.</p>
              </div>
            ) : (
              courses.map((course, idx) => (
                <motion.div
                  key={course.id}
                  className={`${styles.courseCard} glass-card-flat`}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <div className={styles.courseHeader}>
                    <h3 className={styles.courseTitle}>{course.name}</h3>
                    {course.section && <span className={styles.courseSection}>{course.section}</span>}
                  </div>
                  
                  <div className={styles.courseDetails}>
                    <p>Teacher: {course.teacher}</p>
                    <p>{course.assignment_count !== undefined ? course.assignment_count : 0} assignments</p>
                  </div>

                      <div className={styles.courseActions}>
                        {course.is_ingested ? (
                          <div className="flex gap-1">
                            <button 
                              className="btn btn-secondary btn-sm"
                              style={{ borderColor: 'var(--success)', color: 'var(--success)' }}
                              onClick={() => handleIngest(course.id)}
                              disabled={ingesting[course.id]}
                              title="Re-ingest (Sync)"
                            >
                              {ingesting[course.id] ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <RefreshCw size={14} />
                              )}
                              {ingesting[course.id] ? 'Syncing...' : 'Sync'}
                            </button>
                            <button 
                              className="btn btn-secondary btn-sm"
                              onClick={() => toggleIndexManager(course.id)}
                              title="Manage Index"
                            >
                              <RefreshCw size={14} className={showIndexManager[course.id] ? 'rotate-180' : ''} />
                            </button>
                            <button 
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleDeleteIndex(course.id)}
                              disabled={ingesting[course.id]}
                              title="Wipe Index"
                            >
                              <Trash2 size={14} className="text-error" />
                            </button>
                          </div>
                        ) : (
                          <button 
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleIngest(course.id)}
                            disabled={ingesting[course.id]}
                          >
                            {ingesting[course.id] ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <RefreshCw size={14} />
                            )}
                            {ingesting[course.id] ? 'Ingesting...' : 'Ingest'}
                          </button>
                        )}
                        <button 
                          className="btn btn-primary btn-sm"
                          onClick={() => router.push(`/chat/${course.id}`)}
                        >
                          <MessageSquare size={14} />
                          Chat
                        </button>
                      </div>

                      {/* Index Manager Drawer */}
                      {showIndexManager[course.id] && (
                        <div className="mt-4 p-3 rounded-lg bg-black/20 border border-white/5 animate-in slide-in-from-top-2">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-xs font-semibold uppercase tracking-wider opacity-60">Managed Files</span>
                            <span className="text-[10px] opacity-40">{courseFiles[course.id]?.length || 0} documents</span>
                          </div>
                          <div className="space-y-1 max-h-32 overflow-y-auto pr-1 custom-scrollbar">
                            {!courseFiles[course.id] || courseFiles[course.id].length === 0 ? (
                              <div className="text-xs opacity-40 italic py-2">No files indexed for this course yet.</div>
                            ) : (
                              courseFiles[course.id].map((file, fidx) => (
                                <div key={fidx} className="flex justify-between items-center p-2 rounded bg-white/5 hover:bg-white/10 transition-colors">
                                  <div className="flex items-center gap-2 overflow-hidden">
                                    <FileText size={12} className="shrink-0 text-primary" />
                                    <span className="text-xs truncate" title={file.filename}>{file.filename}</span>
                                    <span className="text-[10px] opacity-30 shrink-0">({file.chunk_count} chk)</span>
                                  </div>
                                  <button 
                                    onClick={() => handleDeleteFile(course.id, file.filename)}
                                    className="p-1 hover:text-error transition-colors"
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
        </div>

        {/* Right Column: Weak Topics Sidebar */}
        <aside className={styles.sidebar}>
          <div className={`${styles.weakTopicsCard} glass-card-flat`}>
            <div className={styles.sidebarHeader}>
              <BrainIcon />
              <h3 className="font-display">Learning Focus</h3>
            </div>
            
            <p className={styles.sidebarSub}>
              Based on your conversations, the AI tutor recommends brushing up on these topics.
            </p>

            <div className={styles.topicsList}>
              {!profile?.weak_topics || profile.weak_topics.length === 0 ? (
                <div className={styles.emptyTopics}>
                  No weak topics identified yet. Start chatting to get personalized insights!
                </div>
              ) : (
                profile.weak_topics.map((item, idx) => (
                  <div key={idx} className={styles.topicItem}>
                    <div className={styles.topicName}>{item.topic}</div>
                    <div className={styles.topicCourse}>{item.course_name || 'Across courses'}</div>
                  </div>
                ))
              )}
            </div>

            <button className="btn btn-accent w-full" style={{ width: '100%' }}>
              <Sparkles size={16} />
              Generate Practice Quiz
            </button>
          </div>
        </aside>

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
      <header className={`${styles.header} glass-card`}>
        <div className="skeleton" style={{ width: 120, height: 32 }} />
        <div className="skeleton" style={{ width: 150, height: 32 }} />
      </header>
      <main className={styles.main}>
        <div className={styles.leftColumn}>
          <div className={styles.statsRow}>
            <div className="stat-card skeleton" style={{ height: 100 }} />
            <div className="stat-card skeleton" style={{ height: 100 }} />
            <div className="stat-card skeleton" style={{ height: 100 }} />
          </div>
          <div className="skeleton" style={{ width: 200, height: 32, marginTop: '2rem' }} />
          <div className={styles.courseGrid}>
            {[1, 2, 3, 4].map(k => (
              <div key={k} className="glass-card-flat skeleton" style={{ height: 200 }} />
            ))}
          </div>
        </div>
        <aside className={styles.sidebar}>
          <div className="glass-card-flat skeleton" style={{ height: 400 }} />
        </aside>
      </main>
    </div>
  );
}

function BrainIcon() {
  return (
    <div style={{ background: 'var(--accent-glow)', padding: '0.4rem', borderRadius: '0.5rem', color: 'var(--accent)' }}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>
        <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>
        <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/>
        <path d="M17.599 6.5a3 3 0 0 0 .399-1.375"/>
        <path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/>
        <path d="M3.477 10.896a4 4 0 0 1 .585-.396"/>
        <path d="M19.938 10.5a4 4 0 0 1 .585.396"/>
        <path d="M6 18a4 4 0 0 1-1.967-.516"/>
        <path d="M19.967 17.484A4 4 0 0 1 18 18"/>
      </svg>
    </div>
  );
}

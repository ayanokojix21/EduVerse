'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, BookOpen, AlertCircle, FileText, Calendar, 
  Paperclip, ExternalLink, Video, MessageSquare, Sparkles, 
  RefreshCw, Trash2, Upload, CheckCircle, Loader2
} from 'lucide-react';

import { api } from '@/lib/api';
import type { Course, CourseContent } from '@/types';
import Spinner from '@/components/Spinner';
import styles from './course.module.css';

export default function CoursePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const params = useParams();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [coursework, setCoursework] = useState<CourseContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'assignments' | 'materials' | 'announcements'>('assignments');
  const [syncing, setSyncing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated') fetchCourseData();
  }, [status, courseId]);

  const fetchCourseData = async () => {
    try {
      setLoading(true);
      const [courses, assignments] = await Promise.all([
        api.courses.list(),
        api.courses.getCoursework(courseId)
      ]);
      const found = courses.find((c: Course) => c.id === courseId);
      if (found) setCourse(found);
      setCoursework(assignments);
    } catch (err: any) {
      setError(err.message || 'Failed to load coursework');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!confirm('This will wipe and re-fetch all course materials from Google Classroom. Continue?')) return;
    try {
      setSyncing(true);
      await api.ingestion.sync(courseId);
      await fetchCourseData();
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteIndex = async () => {
    if (!confirm('This will permanently delete all AI knowledge for this course. Continue?')) return;
    try {
      setDeleting(true);
      await api.ingestion.deleteIndex(courseId);
      await fetchCourseData();
    } catch (err: any) {
      alert(err.message || 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) {
      setUploadError('Only PDF files are supported.');
      return;
    }
    try {
      setUploading(true);
      setUploadError(null);
      setUploadSuccess(null);
      await api.ingestion.uploadFile(courseId, file);
      setUploadSuccess(`"${file.name}" successfully ingested!`);
      await fetchCourseData();
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const formatDate = (dueDate?: { year: number; month: number; day: number }) => {
    if (!dueDate) return 'No due date';
    return `${dueDate.month}/${dueDate.day}/${dueDate.year}`;
  };

  if (status === 'loading' || loading) return <CourseSkeleton />;

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <AlertCircle size={40} style={{ color: '#e5484d' }} />
        <h2>Failed to load coursework</h2>
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => router.push('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button onClick={() => router.push('/dashboard')} className="btn btn-ghost btn-sm">
            <ArrowLeft size={14} /> Dashboard
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div className={styles.logoIcon}>
            <BookOpen size={14} />
          </div>
          <span style={{ fontWeight: 600, color: '#ededed' }}>{course?.name}</span>
        </div>
        <div style={{ width: 100 }} />
      </header>

      <main className={styles.main}>
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Hero */}
          <section className={styles.hero}>
            <div className={styles.heroContent}>
              <h1>{course?.name}</h1>
              <p className={styles.heroMeta}>
                {course?.section || 'Active Course'} — Taught by {course?.teacher}
              </p>
            </div>
            <div className={styles.heroActions}>
              <div className={`${styles.statusInfo} ${course?.is_ingested ? styles.statusInfoActive : ''}`}>
                {course?.is_ingested ? (
                  <><CheckCircle size={14} /> AI Ready</>
                ) : (
                  <><AlertCircle size={14} /> Not Ingested</>
                )}
              </div>
              <button 
                onClick={() => router.push(`/chat/${courseId}`)}
                className="btn btn-primary"
                style={{ marginLeft: 'auto' }}
              >
                <MessageSquare size={16} />
                Open AI Tutor
              </button>
            </div>
          </section>

          {/* Content */}
          <section style={{ display: 'flex', flexDirection: 'column' }}>
            <div className={styles.tabBar}>
              <button 
                onClick={() => setActiveTab('assignments')}
                className={`${styles.tabBtn} ${activeTab === 'assignments' ? styles.tabBtnActive : ''}`}
              >
                Assignments ({coursework?.assignments?.length || 0})
              </button>
              <button 
                onClick={() => setActiveTab('materials')}
                className={`${styles.tabBtn} ${activeTab === 'materials' ? styles.tabBtnActive : ''}`}
              >
                Materials ({coursework?.materials?.length || 0})
              </button>
              <button 
                onClick={() => setActiveTab('announcements')}
                className={`${styles.tabBtn} ${activeTab === 'announcements' ? styles.tabBtnActive : ''}`}
              >
                Announcements ({coursework?.announcements?.length || 0})
              </button>
            </div>

            <div className={styles.grid}>
              {!coursework?.[activeTab] || coursework[activeTab].length === 0 ? (
                <div style={{ gridColumn: '1 / -1', padding: '4rem', textAlign: 'center', color: '#6b6b6b' }}>
                  <FileText size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
                  <p>No {activeTab} found for this class.</p>
                </div>
              ) : (
                coursework[activeTab].map(work => (
                  <motion.div 
                    key={work.id}
                    className={styles.card}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className={styles.cardContent}>
                      <h3>{work.title}</h3>
                      {work.description ? (
                        <p className={styles.cardDesc}>{work.description}</p>
                      ) : (
                        <p className={styles.cardDesc} style={{ fontStyle: 'italic' }}>No description provided.</p>
                      )}
                    </div>

                    {work.materials && work.materials.length > 0 && (
                      <div className={styles.materialList}>
                        {work.materials.slice(0, 3).map((mat, idx) => (
                          <div key={idx} className={styles.materialItem}>
                            <Paperclip size={10} />
                            <span>Attachment</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className={styles.cardFooter}>
                      <div className={styles.cardMetaRow}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Calendar size={12} />
                          {formatDate(work.dueDate)}
                        </span>
                        <span className={styles.statusBadge}>{work.state}</span>
                      </div>
                      <div className={styles.cardBtns}>
                        <a 
                          href={work.alternateLink} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="btn btn-ghost btn-sm"
                        >
                          View Source
                        </a>
                        <button 
                          onClick={() => router.push(`/chat/${courseId}?query=Help me understand this ${activeTab.slice(0, -1)}: ${work.title}`)}
                          className="btn btn-primary btn-sm"
                        >
                          <Sparkles size={14} />
                          Ask AI
                        </button>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <aside className={styles.sidebar}>
          <div className={styles.sidebarCard}>
            <div className={styles.sidebarTitle}>
              <BookOpen size={18} style={{ color: '#5e6ad2' }} />
              <span>Course Knowledge</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <button
                onClick={handleSync}
                disabled={syncing || deleting}
                className={`btn btn-ghost ${syncing ? 'btn-loading' : ''}`}
                style={{ width: '100%', justifyContent: 'flex-start' }}
              >
                {!syncing && <RefreshCw size={14} />}
                Sync classroom
              </button>
              <button
                onClick={handleDeleteIndex}
                disabled={deleting || syncing || !course?.is_ingested}
                className={`btn btn-ghost ${deleting ? 'btn-loading' : ''}`}
                style={{ width: '100%', justifyContent: 'flex-start', color: '#e5484d' }}
              >
                {!deleting && <Trash2 size={14} />}
                Wipe AI index
              </button>
            </div>

            <div style={{ paddingTop: '1rem', borderTop: '1px solid #2e2e2e' }}>
              <p style={{ fontSize: '0.7rem', fontWeight: 600, color: '#6b6b6b', textTransform: 'uppercase', marginBottom: '1rem' }}>
                Upload Local Materials
              </p>
              <label className={`${styles.uploadBox} ${uploading ? 'btn-loading' : ''}`} style={{ cursor: uploading ? 'not-allowed' : 'default' }}>
                {!uploading && <Upload size={16} style={{ color: '#5e6ad2' }} />}
                <span style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>
                  {uploading ? 'Processing Document...' : 'Upload PDF'}
                </span>
                <input type="file" accept=".pdf" onChange={handleFileUpload} disabled={uploading} style={{ display: 'none' }} />
              </label>
              {uploadSuccess && <p style={{ color: '#30a46c', fontSize: '0.75rem', marginTop: '0.5rem' }}>✓ {uploadSuccess}</p>}
              {uploadError && <p style={{ color: '#e5484d', fontSize: '0.75rem', marginTop: '0.5rem' }}>✕ {uploadError}</p>}
            </div>

            {/* Attached PDFs */}
            <div style={{ paddingTop: '1rem', borderTop: '1px solid #2e2e2e' }}>
              <p style={{ fontSize: '0.7rem', fontWeight: 600, color: '#6b6b6b', textTransform: 'uppercase', marginBottom: '1rem' }}>
                Course Documents
              </p>
              <div className={styles.attachedList}>
                {coursework && [
                  ...(coursework.assignments || []),
                  ...(coursework.materials || []),
                  ...(coursework.announcements || [])
                ].flatMap(w => w.materials || [])
                  .filter(m => m.driveFile)
                  .map((mat, idx) => (
                  <div key={idx} className={styles.attachedItem}>
                    <span className={styles.attachedName} title={mat.driveFile!.driveFile.title}>
                      {mat.driveFile!.driveFile.title}
                    </span>
                    <a href={mat.driveFile!.driveFile.alternateLink} target="_blank" rel="noopener noreferrer" className={styles.attachedLink}>
                      Open Drive
                    </a>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

function CourseSkeleton() {
  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className="skeleton" style={{ width: 100, height: 28 }} />
        <div className="skeleton" style={{ width: 150, height: 28 }} />
      </header>
      <main className={styles.main}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className={`${styles.hero} skeleton`} style={{ height: 180 }} />
          <div className={styles.grid}>
            {[1, 2, 3, 4].map(k => (
              <div key={k} className={`${styles.card} skeleton`} style={{ height: 240 }} />
            ))}
          </div>
        </div>
        <aside className={styles.sidebar}>
          <div className={`${styles.sidebarCard} skeleton`} style={{ height: 500 }} />
        </aside>
      </main>
    </div>
  );
}

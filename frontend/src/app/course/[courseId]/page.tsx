'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { motion } from 'framer-motion';
import { ArrowLeft, BookOpen, AlertCircle, FileText, Calendar, Paperclip, ExternalLink, Video, MessageSquare, Sparkles, RefreshCw, Trash2, Upload, CheckCircle } from 'lucide-react';

import { api } from '@/lib/api';
import type { Course, CourseContent, CourseItem } from '@/types';
import styles from '../../dashboard/dashboard.module.css';

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
  }, [status]);

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

  if (status === 'loading' || loading) {
    return (
      <div className={styles.root}>
        <div className="skeleton h-full w-full opacity-50" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <AlertCircle size={48} className="text-error" />
        <h2 className="font-display">Failed to load coursework</h2>
        <p>{error}</p>
        <button className="btn btn-primary mt-4" onClick={() => router.push('/dashboard')}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <div className="mesh-bg" aria-hidden style={{ opacity: 0.5 }} />

      <header className={`${styles.header} glass-card`}>
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/dashboard')} className="btn btn-ghost btn-sm">
            <ArrowLeft size={16} /> Dashboard
          </button>
        </div>
        <div className="flex items-center gap-2">
          <div className={styles.logoIcon}>
            <BookOpen size={20} />
          </div>
          <span className="font-display text-lg">{course?.name || 'Classroom'}</span>
        </div>
        <div style={{ width: 100 }} /> {/* Spacer */}
      </header>

      <main style={{ maxWidth: '1400px', width: '100%', margin: '2rem auto', padding: '1.5rem', zIndex: 10, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '2rem', height: 'calc(100vh - 6rem)', overflowY: 'auto' }}>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <section className="glass-card-flat" style={{ padding: '2rem', position: 'relative', overflow: 'hidden' }}>
                <h1 className="font-display" style={{ fontSize: '2.5rem', fontWeight: 500, lineHeight: 1.2, marginBottom: '0.5rem' }}>
                    {course?.name}
                </h1>
                <p className="text-secondary" style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>
                    {course?.section || 'Section n/a'} — Taught by {course?.teacher || 'N/A'}
                </p>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    {course?.is_ingested && (
                        <span className="badge" style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#4ade80' }}>
                            ✅ Ingested for Chat
                        </span>
                    )}
                    <span className="badge badge-secondary">
                        {coursework?.assignments?.length || 0} Assignments
                    </span>
                    <button 
                      onClick={() => router.push(`/chat/${courseId}`)}
                      className="btn btn-primary btn-sm"
                      style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                      <MessageSquare size={16} />
                      Start AI Chat
                    </button>
                </div>
            </section>

        <section style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                <button 
                  onClick={() => setActiveTab('assignments')}
                  style={{ background: 'none', border: 'none', padding: '0.5rem 0', fontWeight: 600, fontSize: '1rem', color: activeTab === 'assignments' ? 'var(--primary)' : 'var(--text-tertiary)', borderBottom: activeTab === 'assignments' ? '2px solid var(--primary)' : '2px solid transparent', cursor: 'pointer', transition: 'all 0.2s' }}
                >
                  Assignments ({coursework?.assignments?.length || 0})
                </button>
                <button 
                  onClick={() => setActiveTab('materials')}
                  style={{ background: 'none', border: 'none', padding: '0.5rem 0', fontWeight: 600, fontSize: '1rem', color: activeTab === 'materials' ? 'var(--primary)' : 'var(--text-tertiary)', borderBottom: activeTab === 'materials' ? '2px solid var(--primary)' : '2px solid transparent', cursor: 'pointer', transition: 'all 0.2s' }}
                >
                  Materials ({coursework?.materials?.length || 0})
                </button>
                <button 
                  onClick={() => setActiveTab('announcements')}
                  style={{ background: 'none', border: 'none', padding: '0.5rem 0', fontWeight: 600, fontSize: '1rem', color: activeTab === 'announcements' ? 'var(--primary)' : 'var(--text-tertiary)', borderBottom: activeTab === 'announcements' ? '2px solid var(--primary)' : '2px solid transparent', cursor: 'pointer', transition: 'all 0.2s' }}
                >
                  Announcements ({coursework?.announcements?.length || 0})
                </button>
            </div>
            
            <div className={styles.courseGrid}>
                {!coursework || !coursework[activeTab] || coursework[activeTab].length === 0 ? (
                    <div style={{ padding: '3rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--tertiary)' }}>
                        <FileText size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                        <p>No {activeTab} found for this class.</p>
                    </div>
                ) : (
                    coursework[activeTab].map(work => (
                        <motion.div 
                            key={work.id}
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            whileHover={{ y: -4, boxShadow: "0 10px 40px -10px rgba(0,0,0,0.5)" }}
                            className={`${styles.courseCard} glass-card-flat`}
                            style={{ minHeight: '220px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '1.5rem' }}
                        >
                            <div>
                                <div className={styles.courseHeader} style={{ marginBottom: '1rem' }}>
                                    <h3 className={styles.courseTitle} style={{ fontSize: '1.125rem', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                        {work.title}
                                    </h3>
                                </div>
                                {work.description ? (
                                    <p className="text-secondary" style={{ fontSize: '0.875rem', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', marginBottom: '1.5rem' }}>
                                        {work.description}
                                    </p>
                                ) : (
                                    <p className="text-tertiary" style={{ fontSize: '0.875rem', fontStyle: 'italic', marginBottom: '1.5rem' }}>
                                        No description provided.
                                    </p>
                                )}
                            </div>
                            
                            {work.materials && work.materials.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.5rem' }}>
                                    {work.materials.map((mat, idx) => {
                                        let icon = <Paperclip size={12} />;
                                        let title = "Attachment";
                                        let link = "#";
                                        
                                        if (mat.driveFile) {
                                            icon = <FileText size={12} />;
                                            title = mat.driveFile.driveFile.title;
                                            link = mat.driveFile.driveFile.alternateLink;
                                        } else if (mat.youtubeVideo) {
                                            icon = <Video size={12} />;
                                            title = mat.youtubeVideo.title;
                                            link = mat.youtubeVideo.alternateLink;
                                        } else if (mat.link) {
                                            icon = <ExternalLink size={12} />;
                                            title = mat.link.title;
                                            link = mat.link.url;
                                        } else if (mat.form) {
                                            icon = <FileText size={12} />;
                                            title = mat.form.title;
                                            link = mat.form.formUrl;
                                        }
                                        
                                        return (
                                            <a 
                                                key={idx}
                                                href={link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.25rem 0.5rem', backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '0.375rem', fontSize: '0.75rem', color: 'var(--text-secondary)', textDecoration: 'none', maxWidth: '100%' }}
                                                title={title}
                                            >
                                                {icon}
                                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>{title}</span>
                                            </a>
                                        );
                                    })}
                                </div>
                            )}
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem', marginTop: 'auto' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--tertiary)' }}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                        <Calendar size={12} />
                                        Due {formatDate(work.dueDate)}
                                    </span>
                                    <span style={{ padding: '0.125rem 0.5rem', borderRadius: '9999px', backgroundColor: work.state === 'PUBLISHED' ? 'rgba(74,222,128,0.2)' : 'rgba(255,255,255,0.1)', color: work.state === 'PUBLISHED' ? '#4ade80' : 'inherit' }}>
                                        {work.state}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <a 
                                        href={work.alternateLink} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="btn btn-secondary"
                                        style={{ flex: 1, fontSize: '0.75rem', padding: '0.5rem 0', textAlign: 'center' }}
                                    >
                                        View
                                    </a>
                                    <button 
                                        onClick={() => router.push(`/chat/${courseId}?query=Help me understand this ${activeTab.slice(0, -1)}: ${work.title}`)}
                                        className="btn btn-primary"
                                        style={{ flex: 1, fontSize: '0.75rem', padding: '0.5rem 0', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
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

        {/* Sidebar: Manage Index */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glass-card-flat" style={{ position: 'sticky', top: '0', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', maxHeight: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ background: 'var(--accent-glow)', padding: '0.4rem', borderRadius: '0.5rem', color: 'var(--accent)' }}>
                        <BookOpen size={20} />
                    </div>
                    <h3 className="font-display" style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>AI Knowledge Base</h3>
                </div>

                {/* Status badge */}
                <div style={{ padding: '0.75rem 1rem', borderRadius: '0.75rem', background: course?.is_ingested ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.05)', border: `1px solid ${course?.is_ingested ? 'rgba(74,222,128,0.3)' : 'var(--border)'}`, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
                    {course?.is_ingested
                        ? <><CheckCircle size={16} color="#4ade80" /> <span style={{ color: '#4ade80' }}>Indexed & Ready for Chat</span></>
                        : <><AlertCircle size={16} color="var(--text-tertiary)" /> <span style={{ color: 'var(--text-tertiary)' }}>Not yet ingested</span></>}
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                    <button
                        onClick={handleSync}
                        disabled={syncing || deleting}
                        className="btn btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%' }}
                    >
                        <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                        {syncing ? 'Syncing from Classroom...' : 'Sync from Classroom'}
                    </button>

                    <button
                        onClick={handleDeleteIndex}
                        disabled={deleting || syncing || !course?.is_ingested}
                        className="btn btn-ghost"
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%', color: 'var(--error, #f87171)', borderColor: 'rgba(248,113,113,0.3)' }}
                    >
                        <Trash2 size={14} />
                        {deleting ? 'Deleting Index...' : 'Delete AI Index'}
                    </button>
                </div>

                {/* Divider */}
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Upload Local PDF</p>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: '0.875rem', lineHeight: 1.5 }}>Add your own notes or textbooks directly into this course's AI knowledge base.</p>

                    <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.65rem 1rem', borderRadius: '0.625rem', border: '1.5px dashed var(--border)', cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.6 : 1, fontSize: '0.875rem', color: 'var(--text-secondary)', transition: 'border-color 0.2s', width: '100%' }}>
                        <Upload size={14} />
                        {uploading ? 'Uploading...' : 'Choose PDF to Upload'}
                        <input type="file" accept=".pdf" onChange={handleFileUpload} disabled={uploading} style={{ display: 'none' }} />
                    </label>

                    {uploadSuccess && (
                        <p style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <CheckCircle size={13} /> {uploadSuccess}
                        </p>
                    )}
                    {uploadError && (
                        <p style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <AlertCircle size={13} /> {uploadError}
                        </p>
                    )}
                </div>

                {/* Attached PDFs list */}
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Attached PDFs</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', overflowY: 'auto', maxHeight: '280px' }}>
                        {coursework && [
                            ...(coursework.assignments || []),
                            ...(coursework.materials || []),
                            ...(coursework.announcements || [])
                          ].flatMap(w => w.materials || [])
                            .filter(m => m.driveFile)
                            .map((mat, idx) => (
                            <div key={idx} style={{ padding: '0.75rem', borderRadius: '0.625rem', background: 'var(--bg-subtle)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                                    <FileText size={12} style={{ flexShrink: 0 }} />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={mat.driveFile!.driveFile.title}>
                                        {mat.driveFile!.driveFile.title}
                                    </span>
                                </div>
                                <a
                                    href={mat.driveFile!.driveFile.alternateLink}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ fontSize: '0.75rem', color: 'var(--secondary)', textDecoration: 'underline' }}
                                >
                                    Open in Drive
                                </a>
                            </div>
                        ))}
                        {coursework && [
                            ...(coursework.assignments || []),
                            ...(coursework.materials || []),
                            ...(coursework.announcements || [])
                          ].flatMap(w => w.materials || []).filter(m => m.driveFile).length === 0 && (
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', textAlign: 'center', padding: '1.5rem 1rem', background: 'var(--bg-subtle)', borderRadius: '0.75rem', border: '1px dashed var(--border)' }}>
                                No PDFs attached to this course.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </aside>

      </main>
    </div>
  );
}

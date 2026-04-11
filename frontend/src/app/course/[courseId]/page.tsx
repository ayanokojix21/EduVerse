'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { motion } from 'framer-motion';
import { ArrowLeft, BookOpen, AlertCircle, FileText, Calendar, Paperclip, ExternalLink, Video } from 'lucide-react';

import { api } from '@/lib/api';
import type { Course, Coursework } from '@/types';
import styles from '../../dashboard/dashboard.module.css';

export default function CoursePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const params = useParams();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [coursework, setCoursework] = useState<Coursework[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

      <main style={{ maxWidth: '1200px', width: '100%', margin: '2rem auto', padding: '1.5rem', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '2rem', height: 'calc(100vh - 6rem)', overflowY: 'auto' }}>
        <section className="glass-card-flat" style={{ padding: '2rem', position: 'relative', overflow: 'hidden' }}>
            <h1 className="font-display" style={{ fontSize: '2.5rem', fontWeight: 500, lineHeight: 1.2, marginBottom: '0.5rem' }}>
                {course?.name}
            </h1>
            <p className="text-secondary" style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>
                {course?.section || 'Section n/a'} — Taught by {course?.teacher || 'N/A'}
            </p>
            <div style={{ display: 'flex', gap: '1rem' }}>
                {course?.is_ingested && (
                    <span className="badge" style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#4ade80' }}>
                        ✅ Ingested for Chat
                    </span>
                )}
                <span className="badge badge-secondary">
                    {coursework.length} Assignments
                </span>
            </div>
        </section>

        <section style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <h2 className="font-display" style={{ fontSize: '1.5rem' }}>Coursework & Assignments</h2>
            </div>
            
            <div className={styles.courseGrid}>
                {coursework.length === 0 ? (
                    <div style={{ padding: '3rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--tertiary)' }}>
                        <FileText size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                        <p>No coursework found for this class.</p>
                    </div>
                ) : (
                    coursework.map(work => (
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
                                            link = mat.form.alternateLink || mat.form.formUrl;
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
                                <a 
                                    href={work.alternateLink} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="btn btn-secondary w-full"
                                    style={{ fontSize: '0.75rem', padding: '0.5rem 0', textAlign: 'center' }}
                                >
                                    View on Classroom
                                </a>
                            </div>
                        </motion.div>
                    ))
                )}
            </div>
        </section>
      </main>
    </div>
  );
}

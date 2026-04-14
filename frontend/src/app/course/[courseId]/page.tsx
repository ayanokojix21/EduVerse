'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { 
  BookOpen, FileText, MessageSquare, ListTree, Sparkles, 
  ChevronRight, ArrowLeft, Calendar, File, Users, Clock,
  Loader2, RefreshCw, Upload
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/Toast';
import type { Course, CourseContent, CourseItem } from '@/types';
import styles from './course.module.css';

export default function CourseHubPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const params = useParams();
  const { showToast } = useToast();
  const courseId = params.courseId as string;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [course, setCourse] = useState<Course | null>(null);
  const [coursework, setCoursework] = useState<CourseContent | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'assignments' | 'materials' | 'announcements' | 'uploaded'>('all');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [courses, courseworkData, filesData] = await Promise.all([
        api.courses.list(),
        api.courses.getCoursework(courseId),
        api.ingestion.listFiles(courseId)
      ]);

      const currentCourse = courses.find((c: Course) => c.id === courseId);
      if (currentCourse) setCourse(currentCourse);
      setCoursework(courseworkData);
      setUploadedFiles(filesData);
    } catch (err) {
      console.error('Failed to load course hub data:', err);
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  const pollIngestionStatus = useCallback(async () => {
    const poll = async () => {
      try {
        const statusData = await api.ingestion.getStatus(courseId);
        if (statusData.status === 'completed') {
          setIsIngesting(false);
          showToast(`Knowledge ingestion complete!`, 'success');
          loadData();
          return true;
        } else if (statusData.status === 'failed') {
          setIsIngesting(false);
          showToast(`Ingestion failed: ${statusData.error || 'Unknown error'}`, 'error');
          return true;
        }
        return false;
      } catch (err) {
        return false;
      }
    };
    const interval = setInterval(async () => {
      const shouldStop = await poll();
      if (shouldStop) clearInterval(interval);
    }, 3000);
  }, [courseId, loadData, showToast]);

  const handleTriggerIngestion = async () => {
    try {
      setIsIngesting(true);
      const response = await api.ingestion.trigger(courseId, true);
      if (response.status === 'accepted') {
        showToast('AI is beginning to learn classroom materials...', 'info');
        pollIngestionStatus();
      } else {
        showToast('Materials indexed successfully', 'success');
        setIsIngesting(false);
        loadData();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to start ingestion', 'error');
      setIsIngesting(false);
    }
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      showToast('Only PDF files are supported currently', 'error');
      return;
    }

    try {
      setIsUploading(true);
      showToast(`Uploading ${file.name}...`, 'info');
      
      const result = await api.ingestion.uploadFile(courseId, file);
      
      showToast(`${file.name} uploaded and indexed successfully!`, 'success');
      loadData(); // Refresh the list
    } catch (err: any) {
      console.error('Upload failed:', err);
      showToast(err.message || 'Failed to upload document', 'error');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  useEffect(() => {
    if (courseId) loadData();
  }, [courseId, loadData]);

  if (loading) return <CourseSkeleton />;
  if (!course) return <div className={styles.emptyState}>Course not found.</div>;

  const filteredItems = () => {
    if (!coursework) return [];
    const { assignments = [], materials = [], announcements = [] } = coursework;
    
    if (activeTab === 'assignments') return assignments;
    if (activeTab === 'materials') return materials;
    if (activeTab === 'announcements') return announcements;
    if (activeTab === 'all') {
      return [...assignments, ...materials, ...announcements].sort((a, b) => 
        new Date(b.creationTime).getTime() - new Date(a.creationTime).getTime()
      );
    }
    return [];
  };

  const getBadgeClass = (type: string) => {
    if (type === 'assignment') return styles.assignmentBadge;
    if (type === 'material') return styles.materialBadge;
    return styles.announcementBadge;
  };

  return (
    <div className={styles.courseHub}>
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleFileChange} 
        accept=".pdf" 
        style={{ display: 'none' }} 
      />
      
      <header className={styles.header}>
        <div className={styles.titleArea}>
          <button onClick={() => router.push('/dashboard')} className="btn btn-ghost btn-sm mb-4 px-0 hover:bg-transparent">
            <ArrowLeft size={16} className="mr-2" /> Back to Dashboard
          </button>
          <h1>{course.name}</h1>
          <p>{course.section || 'General Section'} • {course.teacher}</p>
        </div>
        
        <button 
          onClick={() => router.push(`/chat/${courseId}`)} 
          className={styles.startButton}
        >
          <Sparkles size={20} />
          Start Learning with AI
        </button>
      </header>

      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Total Assignments</span>
          <span className={styles.statValue}>{coursework?.assignments?.length || 0}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Course Materials</span>
          <span className={styles.statValue}>{coursework?.materials?.length || 0}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>AI Ingested Docs</span>
          <span className={styles.statValue}>{uploadedFiles?.length || 0}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Classroom State</span>
          <span className={styles.statValue} style={{ fontSize: '1.25rem', color: '#30a46c' }}>{course.state || 'ACTIVE'}</span>
        </div>
      </div>

      <div className={styles.contentContainer}>
        <aside className={styles.sidebar}>
          <div 
            className={`${styles.navItem} ${activeTab === 'all' ? styles.navActive : ''}`} 
            onClick={() => setActiveTab('all')}
          >
            <ListTree size={18} /> All Content
          </div>
          <div 
            className={`${styles.navItem} ${activeTab === 'assignments' ? styles.navActive : ''}`} 
            onClick={() => setActiveTab('assignments')}
          >
            <FileText size={18} /> Assignments
          </div>
          <div 
            className={`${styles.navItem} ${activeTab === 'materials' ? styles.navActive : ''}`} 
            onClick={() => setActiveTab('materials')}
          >
            <BookOpen size={18} /> Classroom Materials
          </div>
          <div 
            className={`${styles.navItem} ${activeTab === 'announcements' ? styles.navActive : ''}`} 
            onClick={() => setActiveTab('announcements')}
          >
            <MessageSquare size={18} /> Announcements
          </div>
          <div 
            className={`${styles.navItem} ${activeTab === 'uploaded' ? styles.navActive : ''}`} 
            onClick={() => setActiveTab('uploaded')}
          >
            <File size={18} /> Personal Uploads
          </div>
        </aside>

        <main className={styles.mainSection}>
          <div className={styles.sectionHeader}>
            <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</h2>
            {activeTab === 'materials' && (
              <button 
                className="btn btn-primary btn-sm" 
                onClick={handleTriggerIngestion}
                disabled={isIngesting}
              >
                {isIngesting ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Ingest classroom materials
              </button>
            )}
            {activeTab === 'uploaded' && (
              <button 
                className="btn btn-primary btn-sm" 
                onClick={handleFileClick}
                disabled={isUploading}
              >
                {isUploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                Upload Document
              </button>
            )}
          </div>

          <div className={styles.listGrid}>
            {activeTab === 'uploaded' ? (
              uploadedFiles.filter(f => f.source === 'local_upload').length > 0 ? (
                uploadedFiles.filter(f => f.source === 'local_upload').map((file, idx) => (
                  <div key={idx} className={styles.itemCard}>
                    <div className={styles.itemHeader}>
                      <span className={`${styles.typeBadge} ${styles.materialBadge}`}>PDF Document</span>
                    </div>
                    <span className={styles.itemTitle}>{file.filename}</span>
                    <div className={styles.itemFooter}>
                      <span>Manually Uploaded</span>
                      <ChevronRight size={14} />
                    </div>
                  </div>
                ))
              ) : (
                <div className={styles.emptyState}>No personal uploads found for this course.</div>
              )
            ) : (
              filteredItems().length > 0 ? (
                filteredItems().map((item: CourseItem) => (
                  <div key={item.id} className={styles.itemCard} onClick={() => window.open(item.alternateLink, '_blank')}>
                    <div className={styles.itemHeader}>
                      <span className={`${styles.typeBadge} ${getBadgeClass(item.type)}`}>
                        {item.type}
                      </span>
                    </div>
                    <span className={styles.itemTitle}>{item.title}</span>
                    <div className={styles.itemFooter}>
                      <span>{new Date(item.creationTime).toLocaleDateString()}</span>
                      <div className="flex items-center gap-1">
                        View in Classroom
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className={styles.emptyState}>No items found in this category.</div>
              )
            )}
          </div>
        </main>
      </div>

    </div>
  );
}

function CourseSkeleton() {
  return (
    <div className={styles.courseHub}>
      <header className={styles.header}>
        <div className={styles.titleArea}>
          <div className={`${styles.skeleton} ${styles.skeletonTitle}`} />
          <div className={`${styles.skeleton} ${styles.skeletonSubtitle}`} />
        </div>
        <div className={`${styles.skeleton}`} style={{ width: '200px', height: '48px', borderRadius: '8px' }} />
      </header>

      <div className={styles.statsGrid}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={`${styles.skeleton} ${styles.skeletonStat}`} />
        ))}
      </div>

      <div className={styles.contentContainer}>
        <aside className={styles.sidebar}>
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className={`${styles.skeleton} ${styles.skeletonNav}`} />
          ))}
        </aside>
        <main className={styles.mainSection}>
          <div className={`${styles.skeleton}`} style={{ width: '200px', height: '32px', marginBottom: '1.5rem' }} />
          <div className={styles.listGrid}>
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className={`${styles.skeleton} ${styles.skeletonCard}`} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}

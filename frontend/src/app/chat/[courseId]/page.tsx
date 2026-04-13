'use client';

import { useEffect, useState, useRef, FormEvent } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, Send, Sparkles, AlertCircle, ChevronRight, ChevronLeft, 
  Brain, FileText, ListTree, RefreshCw, BookOpen, Plus, MessageSquare, Trash2,
  Mail, Calendar
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { api, API_URL } from '@/lib/api';
import type { 
  Course, CourseContent, CourseItem, Message, SSEEvent, AgentThought, TutorDraft, 
  Explainability, Citation, CriticResult 
} from '@/types';
import styles from './chat.module.css';

// Simple UUID generator for messages
const uuid = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

const NODE_LABELS: Record<string, string> = {
  supervisor: "Analyzing your request...",
  query_rewriter: "Expanding search queries...",
  rag_agent: "Searching Classroom materials...",
  tutor_a: "Drafting concise explanation...",
  tutor_b: "Drafting intuitive analogies...",
  synthesizer: "Merging expert drafts...",
  critic_agent: "Reviewing answer quality...",
  email_agent: "Scanning academic emails...",
  timetable_agent: "Compiling your timetable...",
};

const NODE_ICONS: Record<string, any> = {
  supervisor: RefreshCw,
  query_rewriter: Sparkles,
  rag_agent: BookOpen,
  tutor_a: FileText,
  tutor_b: Brain,
  synthesizer: ListTree,
  critic_agent: AlertCircle,
  email_agent: Mail,
  timetable_agent: Calendar,
};

export default function ChatPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const params = useParams();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [coursework, setCoursework] = useState<CourseContent | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions_list, setSessionsList] = useState<any[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState<string | null>(null);
  
  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState('');
  const [currentThoughts, setCurrentThoughts] = useState<AgentThought[]>([]);
  
  // Inspector state
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'thoughts'|'hivemind'|'citations'|'explain'>('thoughts');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated') {
      loadCourse();
      
      // Handle pre-filled query from URL
      const searchParams = new URLSearchParams(window.location.search);
      const query = searchParams.get('query');
      if (query) {
        setInput(query);
      }
    }
  }, [status]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamBuffer]);

  const loadCourse = async () => {
    try {
      const [courses, assignments, sessionsData] = await Promise.all([
        api.courses.list(),
        api.courses.getCoursework(courseId),
        api.sessions.list(courseId)
      ]);
      const found = courses.find((c: Course) => c.id === courseId);
      if (found) setCourse(found);
      setCoursework(assignments);
      setSessionsList(sessionsData);
    } catch (err) {
      console.error(err);
    }
  };

  const loadSession = async (sid: string) => {
    if (isStreaming) return;
    try {
      setIsLoadingSessions(sid); // track which one is loading
      const fullSession = await api.sessions.get(sid);
      setSessionId(sid);
      // Ensure every message has an id for React keys
      setMessages(fullSession.messages.map((m: any, idx: number) => ({
        ...m,
        id: m.id || `legacy-${idx}-${sid}`,
        timestamp: new Date(m.timestamp)
      })));
      setStreamBuffer('');
      setCurrentThoughts([]);
    } catch (err) {
      console.error("Failed to load session:", err);
    } finally {
      setIsLoadingSessions(null);
    }
  };

  const startNewChat = () => {
    if (isStreaming) return;
    setSessionId(null);
    setMessages([]);
    setStreamBuffer('');
    setCurrentThoughts([]);
  };

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    try {
      await api.sessions.delete(sid);
      setSessionsList(prev => prev.filter(s => s.session_id !== sid));
      if (sessionId === sid) {
        startNewChat();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage: Message = {
      id: uuid(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStreamBuffer('');
    setCurrentThoughts([]);

    // Open inspector to feature the thought process!
    setInspectorOpen(true);
    setActiveTab('thoughts');

    try {
      // Manual SSE parsing using fetch
      const token = (session as any)?.app_jwt;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ 
          message: userMessage.content, 
          course_id: courseId,
          ...(sessionId ? { session_id: sessionId } : {})
        })
      });

      if (!res.ok) throw new Error('Stream failed');
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      
      let buffer = '';
      
      // We'll accumulate the final state from the stream
      let finalBotMessage: Partial<Message> = { 
        id: uuid(),
        role: 'assistant', 
        content: '', 
        timestamp: new Date() 
      };

      while (reader) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || ''; // Keep the last incomplete chunk

        for (const block of blocks) {
          if (!block.trim()) continue;
          const blockLines = block.split('\n');
          let eventName = 'message';
          let eventData = '';
          
          for (const bline of blockLines) {
            if (bline.startsWith('event: ')) {
              eventName = bline.substring(7).trim();
            } else if (bline.startsWith('data: ')) {
              eventData = bline.substring(6).trim();
            }
          }
          
          if (!eventData || eventData === '[DONE]') continue;

          try {
            const dataObj = JSON.parse(eventData);

            if (eventName === 'token') {
              setStreamBuffer(prev => prev + (dataObj.text || ''));
            } 
            else if (eventName === 'agent_thought') {
              setCurrentThoughts(prev => {
                // simple deduplication just in case
                if (prev.some(t => t.node === dataObj.node && t.status === dataObj.status)) return prev;
                return [...prev, dataObj];
              });
            }
            else if (eventName === 'tutor_draft') {
              finalBotMessage.tutor_drafts = [...(finalBotMessage.tutor_drafts || []), dataObj];
            }
            else if (eventName === 'done') {
              if (dataObj.session_id && !sessionId) {
                setSessionId(dataObj.session_id);
              }
              finalBotMessage = {
                ...finalBotMessage,
                content: dataObj.response,
                citations: dataObj.citations,
                explainability: dataObj.explainability,
                critic: dataObj.critic,
                trace_url: dataObj.trace_url
              };
            }
          } catch (e) {
            console.error('SSE Parse Error:', e, block);
          }
        }
      }

      setMessages(prev => [...prev, finalBotMessage as Message]);
      
      // Refresh session list to show new/updated session
      const updatedSessions = await api.sessions.list(courseId);
      setSessionsList(updatedSessions);
      
    } catch (err: any) {
      console.error(err);
      setMessages(prev => [...prev, {
        id: uuid(),
        role: 'assistant',
        content: `**Error:** ${err.message}`,
        timestamp: new Date()        
      }]);
    } finally {
      setIsStreaming(false);
      setStreamBuffer('');
    }
  };

  // Determine which thought log to show (either current active stream, or the last assistant message)
  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant');
  
  return (
    <div className={styles.root}>
      <div className={`${styles.chatMesh} mesh-bg`} />

      {/* ── Left Sidebar (Course Context) ── */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <button onClick={() => router.push('/dashboard')} className={`btn btn-ghost btn-sm ${styles.backBtn}`}>
            <ArrowLeft size={16} /> Back
          </button>
        </div>
        <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', height: 'calc(100vh - 60px)', overflowY: 'auto' }}>
          <div className="glass-card-flat" style={{ padding: '1.25rem', borderRadius: '0.75rem', border: '1px solid var(--border)' }}>
            <h2 className={styles.courseTitle} style={{ fontSize: '1.125rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>{course?.name || 'Loading Course...'}</h2>
            <p className={styles.courseSection} style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>{course?.teacher || 'N/A'}</p>
          </div>
          
          <div style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', padding: '0 0.25rem' }}>
            <p style={{ marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: 'bold', fontSize: '0.75rem', letterSpacing: '0.05em' }}>Session Info</p>
            <p style={{ lineHeight: 1.5 }}>Your AI Tutor has verified access to your Class Drive and assignment rubrics.</p>
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ background: 'var(--accent-glow)', padding: '0.4rem', borderRadius: '0.5rem', color: 'var(--accent)' }}>
                  <MessageSquare size={16} />
                </div>
                <h3 className="font-display" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>Chat History</h3>
              </div>
              <button 
                onClick={startNewChat}
                className="btn btn-ghost btn-xs"
                style={{ color: 'var(--accent)' }}
                title="Start New Chat"
              >
                <Plus size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto', paddingRight: '0.5rem' }}>
              {sessions_list.length === 0 ? (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', textAlign: 'center', padding: '1rem', background: 'var(--bg-subtle)', borderRadius: '0.5rem', border: '1px dashed var(--border)' }}>
                  No past conversations.
                </div>
              ) : (
                sessions_list.map((s) => (
                  <div 
                    key={s.session_id} 
                    onClick={() => loadSession(s.session_id)}
                    className={`${styles.sessionItem} ${sessionId === s.session_id ? styles.activeSession : ''}`}
                    style={{ 
                      padding: '0.75rem', 
                      borderRadius: '0.5rem', 
                      background: sessionId === s.session_id ? 'var(--accent-glow)' : 'var(--bg-subtle)',
                      border: '1px solid',
                      borderColor: sessionId === s.session_id ? 'var(--accent)' : 'var(--border)',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.25rem',
                      position: 'relative',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: '1.5rem' }}>
                      {s.title}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{s.message_count} messages</span>
                      <span>{new Date(s.updated_at).toLocaleDateString()}</span>
                    </div>
                    <button 
                      onClick={(e) => handleDeleteSession(e, s.session_id)}
                      className={styles.deleteSessionBtn}
                      style={{ 
                        position: 'absolute', 
                        right: '0.5rem', 
                        top: '0.75rem', 
                        color: 'var(--text-tertiary)',
                        opacity: 0.6,
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer'
                      }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--accent-glow)', padding: '0.4rem', borderRadius: '0.5rem', color: 'var(--accent)' }}>
                <BookOpen size={16} />
              </div>
              <h3 className="font-display" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>Attached PDFs</h3>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {coursework && [
                        ...(coursework.assignments || []),
                        ...(coursework.materials || []),
                        ...(coursework.announcements || [])
                      ].flatMap(w => w.materials || [])
                    .filter(m => m.driveFile)
                    .map((mat, idx) => (
                    <div key={idx} style={{ padding: '0.875rem 1rem', borderRadius: '0.75rem', background: 'var(--bg-subtle)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                            <FileText size={14} style={{ flexShrink: 0 }} />
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }} title={mat.driveFile!.driveFile.title}>
                                {mat.driveFile!.driveFile.title}
                            </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                            <a 
                                href={mat.driveFile!.driveFile.alternateLink} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                style={{ fontSize: '0.75rem', color: 'var(--secondary)', textDecoration: 'underline' }}
                            >
                                Open
                            </a>
                            {course?.is_ingested ? (
                                <span style={{ fontSize: '0.75rem', color: '#4ade80', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    ✅ Ingested
                                </span>
                            ) : (
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>
                                    Pending
                                </span>
                            )}
                        </div>
                    </div>
                ))}

                {coursework && [
                        ...(coursework.assignments || []),
                        ...(coursework.materials || []),
                        ...(coursework.announcements || [])
                      ].flatMap(w => w.materials || []).filter(m => m.driveFile).length === 0 && (
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', textAlign: 'center', padding: '2rem 1rem', background: 'var(--bg-subtle)', borderRadius: '0.75rem', border: '1px dashed var(--border)' }}>
                        No PDFs attached to this course.
                    </div>
                )}
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Chat Area ── */}
      <main className={styles.mainChat}>
        <header className={styles.chatHeader}>
          <div className="flex items-center gap-3">
            <div className="pulse-dot" style={{ animationPlayState: isStreaming ? 'running' : 'paused' }} />
            <span className="font-display font-medium text-lg">
              {isStreaming ? 'AI is thinking...' : 'EduVerse Tutor'}
            </span>
          </div>
          <button 
            className="btn btn-ghost"
            onClick={() => setInspectorOpen(!inspectorOpen)}
          >
            <AlertCircle size={16} />
            {inspectorOpen ? 'Hide Inspector' : 'Show Inspector'}
          </button>
        </header>

        <section className={styles.messageArea}>
          {messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center opacity-60">
              <Sparkles size={48} className="mb-4 text-primary" />
              <h2 className="font-display text-2xl mb-2">How can I help you learn?</h2>
              <p>Ask a question about your course materials, assignments, or general concepts.</p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`${styles.messageBox} ${msg.role === 'user' ? styles.messageUser : styles.messageAssistant}`}>
              <div className={`${styles.avatar} ${msg.role === 'user' ? styles.avatarUser : styles.avatarBot}`}>
                {msg.role === 'user' ? session?.user?.name?.[0] : <Sparkles size={18} />}
              </div>
              <div className={styles.messageBubble}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
                
                {/* Embedded citations block */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/10 text-xs">
                    <span className="font-semibold text-secondary mb-2 block">Sources Used:</span>
                    <div className="flex flex-wrap gap-2">
                      {msg.citations.map((cit, i) => {
                         // 1. Determine target URL (Prefer file_url for Proxy)
                         let target = cit.file_url || cit.alternate_link || cit.link;
                         if (target && typeof target === 'object') {
                           target = (target as any).url || (target as any).alternateLink;
                         }
                         
                         // 2. Generate finalHref
                         let finalHref = target;
                         
                         if (typeof target === 'string' && target.startsWith('http')) {
                            const isPdf = target.toLowerCase().includes('.pdf') || cit.file_url;
                            
                            if (isPdf) {
                               // Use Proxy for PDFs to enable native #page=N navigation
                               const jwt = (session as any)?.app_jwt;
                               const proxyBase = `${API_URL}/proxy/pdf?url=${encodeURIComponent(target)}${jwt ? `&token=${jwt}` : ''}`;
                               finalHref = cit.page_number ? `${proxyBase}#page=${cit.page_number}` : proxyBase;
                            } else if (cit.page_number) {
                               // Fallback for non-PDF links
                               finalHref = `${target}#page=${cit.page_number}`;
                            }
                         }
                         
                         return (typeof finalHref === 'string' && finalHref !== '#' && finalHref !== '') ? (
                           <a key={i} href={finalHref} target="_blank" rel="noopener noreferrer" className="badge badge-secondary" title={cit.page_number ? `Open on page ${cit.page_number}` : ''}>
                             {cit.source_index ? `[${cit.source_index}] ` : ''}{cit.title} {cit.page_number && `(P. ${cit.page_number})`} ↗
                           </a>
                         ) : (
                           <span key={i} className="badge badge-secondary">{cit.source_index ? `[${cit.source_index}] ` : ''}{cit.title}</span>
                         );
                       })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isStreaming && (
            <div className={`${styles.messageBox} ${styles.messageAssistant}`}>
              <div className={`${styles.avatar} ${styles.avatarBot}`}>
                <Sparkles size={18} />
              </div>
              <div className={styles.messageBubble}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamBuffer}
                </ReactMarkdown>
                <span className={styles.cursorBlink}>|</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </section>

        <div className={styles.inputArea}>
          <AnimatePresence>
            {isStreaming && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className={styles.activeLoader}
              >
                <div className={styles.loaderPulse} />
                <span className="text-sm font-medium">
                  {NODE_LABELS[currentThoughts[currentThoughts.length - 1]?.node] || "AI is thinking..."}
                </span>
              </motion.div>
            )}
          </AnimatePresence>

          <form className={styles.inputCard} onSubmit={handleSend}>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask a question about your course..."
              className={styles.chatInput}
              rows={Math.min(5, input.split('\n').length || 1)}
              disabled={isStreaming}
            />
            <button 
              type="submit" 
              className={`btn btn-primary btn-icon ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
              disabled={isStreaming}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </main>

      {/* ── Right Inspector Panel ── */}
      <aside className={`${styles.inspectorPanel} ${inspectorOpen ? '' : styles.inspectorCollapsed}`}>
        
        <div className={styles.inspectorHandle} onClick={() => setInspectorOpen(!inspectorOpen)}>
          {inspectorOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </div>

        <div className={styles.inspectorHeader}>
          <button className={`${styles.inspectorTab} ${activeTab === 'thoughts' ? styles.active : ''}`} onClick={() => setActiveTab('thoughts')}>
            <ListTree size={14} className="inline mr-1" /> Brain
          </button>
          <button className={`${styles.inspectorTab} ${activeTab === 'hivemind' ? styles.active : ''}`} onClick={() => setActiveTab('hivemind')}>
            <Brain size={14} className="inline mr-1" /> HiveMind
          </button>
          <button className={`${styles.inspectorTab} ${activeTab === 'citations' ? styles.active : ''}`} onClick={() => setActiveTab('citations')}>
            <FileText size={14} className="inline mr-1" /> Sources
          </button>
        </div>

        <div className={styles.inspectorBody}>
          {activeTab === 'thoughts' && (
            <div className={styles.thoughtsList}>
              {currentThoughts.length === 0 && !isStreaming ? (
                <p className="text-sm text-tertiary">No active brain processes. Ask a question to see the AI think!</p>
              ) : (
                (() => {
                  // Group thoughts for parallel visualization
                  const groups: any[] = [];
                  let currentParallelGroup: any[] = [];

                  currentThoughts.forEach((thought) => {
                    if (thought.node === 'tutor_a' || thought.node === 'tutor_b') {
                      currentParallelGroup.push(thought);
                      if (currentParallelGroup.length === 2) {
                        groups.push({ type: 'parallel', thoughts: [...currentParallelGroup] });
                        currentParallelGroup = [];
                      }
                    } else {
                      if (currentParallelGroup.length > 0) {
                        groups.push({ type: 'parallel', thoughts: [...currentParallelGroup] });
                        currentParallelGroup = [];
                      }
                      groups.push({ type: 'single', thought });
                    }
                  });
                  if (currentParallelGroup.length > 0) {
                    groups.push({ type: 'parallel', thoughts: currentParallelGroup });
                  }

                  return (
                    <div style={{ position: 'relative' }}>
                      <AnimatePresence mode="popLayout">
                        {groups.map((group, idx) => {
                          const isParallel = group.type === 'parallel';
                          return (
                            <motion.div 
                              key={idx}
                              initial={{ opacity: 0, scale: 0.9, y: 20 }}
                              animate={{ opacity: 1, scale: 1, y: 0 }}
                              transition={{ duration: 0.4, delay: idx * 0.1 }}
                              className="mb-8"
                            >
                              {isParallel ? (
                                <div className={styles.parallelStepWrapper}>
                                  <div className={styles.parallelStepLabel}>Parallel Synthesis</div>
                                  <div className={styles.parallelStepContainer}>
                                    {group.thoughts.map((thought: any, tid: number) => {
                                      const Icon = NODE_ICONS[thought.node] || Brain;
                                      return (
                                        <motion.div 
                                          key={tid} 
                                          className={`${styles.flowNode} ${thought.status === 'active' ? styles.activeNode : ''}`}
                                          style={{ width: '160px' }}
                                        >
                                          <div className="flex items-center gap-2 mb-2">
                                            <div className={`${styles.nodeIcon} ${styles[thought.status]}`}>
                                              <Icon size={12} />
                                            </div>
                                            <span className="text-[10px] font-bold uppercase tracking-wider opacity-60">
                                              {thought.node.replace('_agent', '').replace('_', ' ')}
                                            </span>
                                          </div>
                                          <p className="text-[11px] leading-tight text-secondary">
                                            {thought.summary}
                                          </p>
                                          {thought.data && (
                                            <div className="mt-2 pt-2 border-t border-white/5 flex flex-col gap-1">
                                              {thought.data.reasoning && (
                                                <p className="text-[9px] italic text-tertiary line-clamp-2">
                                                  &quot;{thought.data.reasoning}&quot;
                                                </p>
                                              )}
                                              <div className="flex gap-1">
                                                {thought.data.citation_count !== undefined && (
                                                  <span className="text-[8px] bg-secondary/20 text-secondary px-1.5 py-0.5 rounded">
                                                    {thought.data.citation_count} Citations
                                                  </span>
                                                )}
                                              </div>
                                            </div>
                                          )}
                                        </motion.div>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : (
                                <div className={`${styles.flowNode} ${group.thought.status === 'active' ? styles.activeNode : ''}`}>
                                  <div className="flex items-center gap-3 mb-2">
                                    <div className={`${styles.nodeIcon} ${styles[group.thought.status]}`}>
                                      {(() => {
                                        const Icon = NODE_ICONS[group.thought.node] || Sparkles;
                                        return <Icon size={14} />;
                                      })()}
                                    </div>
                                    <span className="text-xs font-bold uppercase tracking-wider">
                                      {group.thought.node.replace('_agent', '').replace('_', ' ')}
                                    </span>
                                    {group.thought.status === 'active' && <div className={styles.loaderPulse} style={{ width: 6, height: 6 }} />}
                                  </div>
                                  <p className="text-sm text-secondary">
                                    {group.thought.summary}
                                  </p>

                                  {/* Rich Decision Data */}
                                  {group.thought.data && Object.keys(group.thought.data).length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-white/5 flex flex-col gap-2">
                                      {group.thought.data.queries && (
                                        <div className="flex flex-wrap gap-1">
                                          {group.thought.data.queries.map((q: string, i: number) => (
                                            <span key={i} className="text-[10px] bg-white/5 px-2 py-0.5 rounded border border-white/10 text-tertiary">
                                              "{q}"
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                      {group.thought.data.consensus_reasoning && (
                                        <div className="text-[11px] italic text-accent bg-accent-glow/20 p-2 rounded border border-accent/20">
                                          <span className="font-bold uppercase text-[9px] block mb-1 opacity-70">Consensus Strategy</span>
                                          {group.thought.data.consensus_reasoning}
                                        </div>
                                      )}
                                      {group.thought.data.issues && group.thought.data.issues.length > 0 && (
                                        <div className="flex flex-col gap-1">
                                          <span className="text-[9px] font-bold uppercase opacity-60">Quality Issues:</span>
                                          {group.thought.data.issues.map((issue: string, i: number) => (
                                            <div key={i} className="text-[10px] text-red-400 bg-red-400/5 p-1.5 rounded border border-red-400/10 flex gap-2">
                                              <span>•</span> {issue}
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                      <div className="flex flex-wrap gap-2">
                                        {group.thought.data.task && <span className="badge badge-secondary text-[9px] h-4">Task: {group.thought.data.task}</span>}
                                        {group.thought.data.difficulty && <span className="badge badge-accent text-[9px] h-4">Diff: {group.thought.data.difficulty}</span>}
                                        {group.thought.data.retrieval_ms && <span className="text-[9px] bg-white/5 px-1.5 py-0.5 rounded opacity-60">Latency: {group.thought.data.retrieval_ms}ms</span>}
                                        {group.thought.data.confidence_score !== undefined && (
                                          <span className="text-[9px] bg-success/10 text-success px-1.5 py-0.5 rounded">
                                            Match: {(group.thought.data.confidence_score * 100).toFixed(1)}%
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Visual Connector Line */}
                              {idx < groups.length - 1 && (
                                <div style={{ height: '32px', display: 'flex', justifyContent: 'center', opacity: 0.5 }}>
                                  <svg width="4" height="32">
                                    <motion.line 
                                      x1="2" y1="0" x2="2" y2="32"
                                      className={styles.connectorLine}
                                      strokeLinecap="round"
                                      initial={{ pathLength: 0 }}
                                      animate={{ pathLength: 1 }}
                                      transition={{ duration: 0.5 }}
                                    />
                                  </svg>
                                </div>
                              )}
                            </motion.div>
                          );
                        })}
                      </AnimatePresence>
                    </div>
                  );
                })()
              )}
            </div>
          )}

          {activeTab === 'hivemind' && (
            <div className={styles.hivemindContainer}>
              {(!lastAssistantMsg?.tutor_drafts || lastAssistantMsg.tutor_drafts.length === 0) ? (
                <p className="text-sm text-tertiary">No alternative drafts available for this response.</p>
              ) : (
                lastAssistantMsg.tutor_drafts.map((draft, i) => (
                  <div key={i} className={styles.draftCard}>
                    <div className={styles.draftHeader}>
                      <span>{draft.agent_id}</span>
                      <span className="badge badge-accent badge-sm">{draft.style}</span>
                    </div>
                    <div className={styles.draftContent}>{draft.response_text}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'citations' && (
            <div>
              {(!lastAssistantMsg?.citations || lastAssistantMsg.citations.length === 0) ? (
                <p className="text-sm text-tertiary">No sources were retrieved for the last answer.</p>
              ) : (
                lastAssistantMsg.citations.map((cit, i) => {
                  let href = cit.alternate_link || cit.link;
                  if (href && typeof href === 'object') {
                    href = (href as any).url || (href as any).alternateLink;
                  }
                  
                  return (
                    <div key={i} className={styles.citationCard}>
                      <div className={styles.citationTitle}>
                        {typeof href === 'string' ? (
                          <a href={href} target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors">
                            {cit.title} ↗
                          </a>
                        ) : (
                          cit.title
                        )}
                      </div>
                      {cit.score && <div className={styles.citationScore}>Relevance: {(cit.score * 100).toFixed(1)}%</div>}
                      {cit.snippet && <p className="text-xs text-tertiary mt-2">{cit.snippet}</p>}
                    </div>
                  );
                })
              )}
              
              {/* Explainability Block */}
              {lastAssistantMsg?.explainability && (
                <div className="mt-8 pt-4 border-t border-strong">
                  <h4 className="font-display text-sm mb-3">Retrieval Trace</h4>
                  <div className="flex flex-col gap-2 text-xs text-secondary">
                    <div className="flex justify-between">
                      <span>Label:</span> 
                      <span className="font-bold text-primary">{lastAssistantMsg.explainability.retrieval_label}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Confidence:</span> 
                      <span className={`badge ${lastAssistantMsg.explainability.confidence_label === 'High' ? 'badge-success' : 'badge-warning'}`}>
                        {lastAssistantMsg.explainability.confidence_label}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

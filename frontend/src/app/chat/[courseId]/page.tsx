'use client';

import React, { useEffect, useState, useRef, FormEvent, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, Send, Sparkles, AlertCircle, ChevronRight, ChevronLeft, 
  Brain, FileText, ListTree, RefreshCw, BookOpen, Plus, MessageSquare, Trash2,
  Mail, Calendar, Loader2, CheckCircle
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import { useToast } from '@/components/Toast';

import 'katex/dist/katex.min.css';

import { api, API_URL } from '@/lib/api';
import Spinner from '@/components/Spinner';
import type { 
  Course, CourseContent, Message, SSEEvent, AgentThought, TutorDraft, 
  Explainability, Citation, CriticResult 
} from '@/types';
import styles from './chat.module.css';

/**
 * Shared utility to resolve a citation to its final link (handling PDF proxies).
 */
const resolveCitationUrl = (cit: Citation, session: any) => {
  let target = cit.file_url || cit.alternate_link || cit.link;
  if (!target || typeof target !== 'string') return '#';
  
  if (target.startsWith('http')) {
     const isPdf = target.toLowerCase().includes('.pdf') || cit.file_url;
     if (isPdf) {
        const jwt = session?.app_jwt;
        const proxyBase = `${API_URL}/proxy/pdf?url=${encodeURIComponent(target)}${jwt ? `&token=${jwt}` : ''}`;
        return cit.page_number ? `${proxyBase}#page=${cit.page_number}` : proxyBase;
     } else if (cit.page_number) {
        return `${target}#page=${cit.page_number}`;
     }
  }
  return target;
};

const uuid = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

/**
 * Robustly converts various math delimiters to standard $ and $$ 
 * and transforms [1] citations into direct links if URLs are available.
 */
const preprocessMarkdown = (content: string, citations?: Citation[], session?: any) => {
  if (!content) return "";
  
  // 1. Convert \( ... \) to $ ... $
  let processed = content.replace(/\\\((.*?)\\\)/g, "$ $1 $");
  
  // 2. Convert \[ ... \] to $$ ... $$
  processed = processed.replace(/\\\[(.*?)\\\]/g, "$$\n$1\n$$");

  // 3. Heuristic: Find math-like content in parentheses (e.g. z = \sum_i...) and wrap in $
  // This is a safety for model slips. We look for backslashes, underscores, or carets inside (...)
  processed = processed.replace(/(\s)\(([^)]*?[\\_^{][^)]*?)\)(\s|\.|\,|$)/g, "$1$ $2 $ $3");

  // 4. Convert citations [1] or [1, 2] to superscripts
  processed = processed.replace(/\[(\d+(?:,\s*\d+)*)\]/g, (match, indices) => {
    const parts = indices.split(',').map((i: string) => i.trim());
    const links = parts.map((idxStr: string) => {
      const idx = parseInt(idxStr);
      let href = `#cit-${idx}`; // Fallback to anchor
      
      // If we have citation metadata, resolve to direct link
      if (citations && citations[idx - 1]) {
        href = resolveCitationUrl(citations[idx - 1], session);
      }
      
      return `<a href="${href}" ${href.startsWith('http') ? 'target="_blank" rel="noopener noreferrer"' : ''} class="cit-link">${idxStr}</a>`;
    }).join(',');
    return `<sup>${links}</sup>`;
  });

  return processed;
};

const NODE_LABELS: Record<string, string> = {
  orchestrator: "Analyzing & Strategic Planning",
  supervisor: "Analyzing request",
  query_rewriter: "Expanding search",
  rag_agent: "Searching Classroom",
  tutor_a: "Drafting explanation",
  tutor_b: "Drafting analogies",
  synthesizer: "Merging drafts",
  critic_agent: "Reviewing quality",
  email_agent: "Scanning emails",
  timetable_agent: "Compiling timetable",
};

const NODE_ICONS: Record<string, any> = {
  orchestrator: RefreshCw,
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

const NODE_DESCRIPTIONS: Record<string, string> = {
  supervisor: "Determining the best way to answer your query based on current context.",
  query_rewriter: "Generating optimized search terms to find the most relevant course materials.",
  rag_agent: "Searching through your Google Classroom documents, materials, and assignments.",
  tutor_a: "Crafting a clear, step-by-step explanation grounded in course content.",
  tutor_b: "Developing helpful analogies and examples to simplify complex concepts.",
  synthesizer: "Combining responses and ensuring everything is accurate and consistent.",
  critic_agent: "Performing a final quality check to ensure the answer meets educational standards.",
  email_agent: "Scanning your classroom announcements for recent updates or deadlines.",
  timetable_agent: "Organizing schedule information into a clear, readable format.",
};

const PIPELINE_STEPS = [
  { id: 'planning', type: 'single', nodes: ['orchestrator', 'supervisor', 'query_rewriter'], label: 'Strategic Planning' },
  { id: 'rag_agent', type: 'single', label: 'Searching Classroom' },
  { id: 'parallel_tutors', type: 'parallel', nodes: ['tutor_a', 'tutor_b'] },
  { id: 'synthesizer', type: 'single', label: 'Synthesizing Response' },
  { id: 'critic_agent', type: 'single', label: 'Final Quality Audit' }
] as const;

export default function ChatPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const { showToast } = useToast();
  const params = useParams();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [coursework, setCoursework] = useState<CourseContent | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions_list, setSessionsList] = useState<any[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState<string | null>(null);
  
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState('');
  const [currentThoughts, setCurrentThoughts] = useState<AgentThought[]>([]);
  
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'thoughts'|'hivemind'|'citations'|'explain'>('thoughts');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadCourse = useCallback(async () => {
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
  }, [courseId]);

  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated') {
      loadCourse();
      const searchParams = new URLSearchParams(window.location.search);
      const query = searchParams.get('query');
      if (query) setInput(query);
    }
  }, [status, courseId, router, loadCourse]);

  const loadSession = async (sid: string) => {
    if (isStreaming) return;
    try {
      setIsLoadingSessions(sid);
      const fullSession = await api.sessions.get(sid);
      setSessionId(sid);
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
    if (!confirm('Delete this conversation?')) return;
    try {
      await api.sessions.delete(sid);
      setSessionsList(prev => prev.filter(s => s.session_id !== sid));
      if (sessionId === sid) startNewChat();
      showToast('Session deleted', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to delete session', 'error');
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
    setInspectorOpen(true);
    setActiveTab('thoughts');

    try {
      const token = (session as any)?.app_jwt;
      const res = await fetch(`${API_URL}/chat/stream`, {
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
        buffer = blocks.pop() || '';

        for (const block of blocks) {
          if (!block.trim()) continue;
          const blockLines = block.split('\n');
          let eventName = 'message';
          let eventData = '';
          for (const bline of blockLines) {
            if (bline.startsWith('event: ')) eventName = bline.substring(7).trim();
            else if (bline.startsWith('data: ')) eventData = bline.substring(6).trim();
          }
          if (!eventData || eventData === '[DONE]') continue;

          try {
            const dataObj = JSON.parse(eventData);
            if (eventName === 'token') setStreamBuffer(prev => prev + (dataObj.text || ''));
            else if (eventName === 'agent_thought') {
              setCurrentThoughts(prev => {
                if (prev.some(t => t.node === dataObj.node && t.status === dataObj.status)) return prev;
                return [...prev, dataObj];
              });
            }
            else if (eventName === 'tutor_draft') finalBotMessage.tutor_drafts = [...(finalBotMessage.tutor_drafts || []), dataObj];
            else if (eventName === 'done') {
              if (dataObj.session_id && !sessionId) setSessionId(dataObj.session_id);
              finalBotMessage = {
                ...finalBotMessage,
                content: dataObj.response,
                citations: dataObj.citations,
                explainability: dataObj.explainability,
                critic: dataObj.critic,
                thoughts: currentThoughts,
                trace_url: dataObj.trace_url
              };
            }
          } catch (e) {}
        }
      }
      setMessages(prev => [...prev, finalBotMessage as Message]);
      const updatedSessions = await api.sessions.list(courseId);
      setSessionsList(updatedSessions);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: uuid(), role: 'assistant', content: `**Error:** ${err.message}`, timestamp: new Date()        
      }]);
    } finally {
      setIsStreaming(false);
      setStreamBuffer('');
    }
  };

  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant');

  return (
    <div className={styles.root}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <button onClick={() => router.push('/dashboard')} className={styles.backBtn}>
            <ArrowLeft size={16} /> Back
          </button>
        </div>
        
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
          <div style={{ paddingBottom: '1.5rem', borderBottom: '1px solid #2e2e2e', marginBottom: '1.5rem' }}>
            <h2 className={styles.courseTitle}>{course?.name || 'Loading...'}</h2>
            <p className={styles.courseSection}>{course?.teacher}</p>
          </div>

          <div style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#6b6b6b', textTransform: 'uppercase' }}>History</span>
              <button onClick={startNewChat} className="btn-ghost" title="New chat"><Plus size={14} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              {sessions_list.map(s => (
                <div 
                  key={s.session_id} 
                  onClick={() => loadSession(s.session_id)}
                  className={`${styles.sessionItem} ${sessionId === s.session_id ? styles.activeSession : ''}`}
                >
                   <span className={styles.sessionTitle}>{s.title}</span>
                   <div className={styles.sessionActions}>
                     {isLoadingSessions === s.session_id ? (
                       <Spinner size={12} color="#5e6ad2" />
                     ) : (
                       <button 
                         className={styles.deleteSessionBtn} 
                         onClick={(e) => handleDeleteSession(e, s.session_id)}
                         title="Delete session"
                       >
                         <Trash2 size={12} />
                       </button>
                     )}
                   </div>
                </div>
              ))}
            </div>
          </div>

          <div>
             <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#6b6b6b', textTransform: 'uppercase', marginBottom: '1rem', display: 'block' }}>Course Materials</span>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {coursework && [
                  ...(coursework.assignments || []),
                  ...(coursework.materials || []),
                  ...(coursework.announcements || [])
                ].flatMap(w => w.materials || [])
                  .filter(m => m.driveFile)
                  .map((mat, idx) => (
                  <div key={idx} style={{ padding: '0.625rem', borderRadius: '4px', background: '#161616', border: '1px solid #2e2e2e', fontSize: '0.8rem' }}>
                    <div style={{ color: '#ededed', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mat.driveFile!.driveFile.title}</div>
                    <a href={mat.driveFile!.driveFile.alternateLink} target="_blank" rel="noopener noreferrer" style={{ color: '#5e6ad2', fontSize: '0.7rem' }}>View Drive</a>
                  </div>
                ))}
             </div>
          </div>
        </div>
      </aside>

      {/* Main Chat */}
      <main className={styles.mainChat}>
        <header className={styles.chatHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className={isStreaming ? styles.loaderPulse : ''} style={{ width: 8, height: 8, borderRadius: '50%', background: '#30a46c' }} />
            <span style={{ fontWeight: 600 }}>EduVerse AI</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => setInspectorOpen(!inspectorOpen)}>
            {inspectorOpen ? 'Hide' : 'Inspect'} Brain
          </button>
        </header>

        <div className={styles.messageArea}>
          {messages.length === 0 && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.4 }}>
              <Sparkles size={40} style={{ marginBottom: '1rem' }} />
              <p>Start a conversation to begin learning.</p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`${styles.messageBox} ${msg.role === 'user' ? styles.messageUser : styles.messageAssistant}`}>
              <div className={`${styles.avatar} ${msg.role === 'user' ? styles.avatarUser : styles.avatarBot}`}>
                {msg.role === 'user' ? session?.user?.name?.[0] : 'AI'}
              </div>
              <div className={styles.messageBubble}>
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex, rehypeRaw]}
                >
                  {preprocessMarkdown(msg.content, msg.citations, session)}
                </ReactMarkdown>
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid #2e2e2e', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {msg.citations.map((cit, i) => {
                       const finalHref = resolveCitationUrl(cit, session);

                       return (finalHref && finalHref !== '#') ? (
                         <a 
                           key={i} 
                           id={`cit-${i+1}`}
                           href={finalHref as string} 
                           target="_blank" 
                           rel="noopener noreferrer" 
                           className="badge badge-secondary"
                           style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '0.25rem', textDecoration: 'none' }}
                         >
                           {cit.title} {cit.page_number && `(p. ${cit.page_number})`} ↗
                         </a>
                       ) : (
                         <span key={i} className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>
                           {cit.title}
                         </span>
                       );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isStreaming && (
            <div className={`${styles.messageBox} ${styles.messageAssistant}`}>
              <div className={`${styles.avatar} ${styles.avatarBot}`}>AI</div>
              <div className={styles.messageBubble}>
                {/* Thinking Mode Block */}
                <div className={styles.thinkingBlock}>
                   <div className={styles.thinkingHeader}>
                      <Spinner size={14} color="#5e6ad2" />
                      <span className={styles.thinkingTitle}>AI is thinking...</span>
                   </div>
                   {currentThoughts.map((t, i) => {
                      const Icon = NODE_ICONS[t.node] || Sparkles;
                      const isActive = i === currentThoughts.length - 1;
                      return (
                        <div key={i} className={`${styles.thoughtStep} ${isActive ? styles.thoughtStepActive : styles.thoughtStepDone}`}>
                          <div className={`${styles.thoughtIcon} ${isActive ? styles.pulseIcon : ''}`}>
                            <Icon size={14} />
                          </div>
                          <div className={styles.thoughtContent}>
                            <div className={styles.thoughtLabel}>{NODE_LABELS[t.node]}</div>
                            {isActive && <div className={styles.thoughtDetail}>{NODE_DESCRIPTIONS[t.node]}</div>}
                          </div>
                        </div>
                      );
                   })}
                </div>
                
                {streamBuffer && (
                  <div style={{ marginTop: '1.5rem', borderTop: '1px solid #1f1f1f', paddingTop: '1.5rem' }}>
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex, rehypeRaw]}
                    >
                      {preprocessMarkdown(streamBuffer)}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className={styles.inputArea}>
          {isStreaming && (
            <div className={styles.activeLoader}>
               <div className={styles.loaderPulse} />
               <span>{NODE_LABELS[currentThoughts[currentThoughts.length - 1]?.node] || 'Thinking...'}</span>
            </div>
          )}
          <form className={styles.inputCard} onSubmit={handleSend}>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Ask anything..."
              className={styles.chatInput}
              disabled={isStreaming}
            />
            <button type="submit" className="btn btn-primary btn-icon" disabled={isStreaming}><Send size={16} /></button>
          </form>
        </div>
      </main>

      {/* Inspector */}
      <aside className={`${styles.inspectorPanel} ${inspectorOpen ? '' : styles.inspectorCollapsed}`}>
        <div className={styles.inspectorHandle} onClick={() => setInspectorOpen(!inspectorOpen)}>
          {inspectorOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </div>
        <div className={styles.inspectorHeader}>
          <button className={`${styles.inspectorTab} ${activeTab === 'thoughts' ? styles.active : ''}`} onClick={() => setActiveTab('thoughts')}>Process Log</button>
        </div>
        <div className={styles.inspectorBody}>
           {activeTab === 'thoughts' && (
             <div className={styles.pipelineContainer}>
                {PIPELINE_STEPS.map((step, sidx) => {
                  const isLastStep = sidx === PIPELINE_STEPS.length - 1;
                  const lastThought = currentThoughts[currentThoughts.length - 1];
                  
                  if (step.type === 'single') {
                    const nodeIds = (step as any).nodes || [step.id];
                    const isDone = currentThoughts.some(t => nodeIds.includes(t.node));
                    const isActive = lastThought && nodeIds.includes(lastThought.node) && isStreaming;
                    const displayId = step.id === 'planning' ? 'supervisor' : step.id;
                    const Icon = NODE_ICONS[displayId as string] || Sparkles;

                    return (
                      <React.Fragment key={step.id}>
                        <div className={`
                          ${styles.pipelineNode} 
                          ${!isActive && !isDone ? styles.pipelineNodePending : ''} 
                          ${isActive ? styles.pipelineNodeActive : ''} 
                          ${isDone && !isActive ? styles.pipelineNodeDone : ''}
                        `}>
                          <div className={`${styles.nodeIcon} ${isDone ? styles.nodeIconDone : ''} ${isActive ? styles.pulseIcon : ''}`}>
                             <Icon size={16} />
                          </div>
                          <span className={styles.nodeLabel}>{(step as any).label || NODE_LABELS[step.id as string]}</span>
                          {isDone && !isActive && <CheckCircle size={12} style={{ marginLeft: 'auto', color: '#30a46c' }} />}
                        </div>
                        {!isLastStep && (
                          <div className={`${styles.connectorLine} ${isDone ? styles.connectorLineActive : ''}`} />
                        )}
                      </React.Fragment>
                    );
                  } else {
                    // Parallel Tutors
                    const isTutorADone = currentThoughts.some(t => t.node === 'tutor_a');
                    const isTutorBDone = currentThoughts.some(t => t.node === 'tutor_b');
                    const isAnyTutorProcessed = isTutorADone || isTutorBDone;

                    return (
                      <React.Fragment key={step.id}>
                        <div className={styles.splitLineContainer}>
                           <div className={`${styles.splitLine} ${isAnyTutorProcessed ? styles.splitLineActive : ''}`} />
                        </div>
                        <div className={styles.parallelWrapper}>
                          {step.nodes.map(nid => {
                            const isDone = currentThoughts.some(t => t.node === nid);
                            const isActive = lastThought?.node === nid && isStreaming;
                            const Icon = NODE_ICONS[nid] || Sparkles;

                            return (
                              <div key={nid} className={`
                                ${styles.pipelineNode} 
                                ${!isActive && !isDone ? styles.pipelineNodePending : ''} 
                                ${isActive ? styles.pipelineNodeActive : ''} 
                                ${isDone && !isActive ? styles.pipelineNodeDone : ''}
                              `}>
                                <div className={`${styles.nodeIcon} ${isDone ? styles.nodeIconDone : ''} ${isActive ? styles.pulseIcon : ''}`}>
                                   <Icon size={16} />
                                </div>
                                <span className={styles.nodeLabel}>{NODE_LABELS[nid]}</span>
                                {isDone && !isActive && <CheckCircle size={12} style={{ marginLeft: 'auto', color: '#30a46c' }} />}
                              </div>
                            );
                          })}
                        </div>
                        <div className={styles.splitLineContainer} style={{ transform: 'rotate(180deg)' }}>
                           <div className={`${styles.splitLine} ${isTutorADone && isTutorBDone ? styles.splitLineActive : ''}`} />
                        </div>
                        <div className={`${styles.connectorLine} ${isTutorADone && isTutorBDone ? styles.connectorLineActive : ''}`} />
                      </React.Fragment>
                    );
                  }
                })}
             </div>
           )}
        </div>
      </aside>
    </div>
  );
}

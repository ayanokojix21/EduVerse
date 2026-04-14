'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldCheck, ArrowLeft, Activity, Target, Zap, 
  ExternalLink, ChevronRight, Clock, RefreshCw, AlertCircle
} from 'lucide-react';
import { useSession } from 'next-auth/react';
import Image from 'next/image';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import 'katex/dist/katex.min.css';

import { api } from '@/lib/api';
import Spinner from '@/components/Spinner';
import styles from './rl.module.css';

interface RLStats {
  global_performance: {
    avg_reward: number;
    total_episodes: number;
    last_run: string;
  };
  environment_standard: string;
  status: string;
}

interface RLEpisode {
  query: string;
  response: string;
  reward: number;
  review: {
    severity: 'none' | 'low' | 'high';
    issues: string[];
    passed: boolean;
    required_facts?: string[];
  };
  timestamp: string;
}

const preprocessMarkdown = (content: string) => {
  if (!content) return "";
  // Convert \( ... \) to $ ... $ and \[ ... \] to $$ ... $$
  let processed = content.replace(/\\\((.*?)\\\)/g, "$ $1 $");
  processed = processed.replace(/\\\[(.*?)\\\]/g, "$$\n$1\n$$");
  return processed;
};

export default function RLDashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  
  const [stats, setStats] = useState<RLStats | null>(null);
  const [episodes, setEpisodes] = useState<RLEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedIndices, setExpandedIndices] = useState<number[]>([]);

  const toggleRow = (idx: number) => {
    setExpandedIndices(prev => 
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };

  const fetchData = async () => {
    try {
      setIsRefreshing(true);
      const [statsData, episodesData] = await Promise.all([
        api.rl.getStats(),
        api.rl.listEpisodes(30)
      ]);
      setStats(statsData);
      setEpisodes(episodesData);
      setError(null);
    } catch (err: any) {
      console.error('RL Dashboard error:', err);
      setError(err.message || 'Failed to fetch RL monitoring data');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace('/');
    } else if (status === 'authenticated') {
      fetchData();
    }
  }, [status, router]);

  if (loading && !isRefreshing) return <LogicAuditsSkeleton />;

  return (
    <div className={styles.root}>
      {/* ── Header ── */}
      <header className={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div className={styles.logoRow} onClick={() => router.push('/dashboard')}>
             <div className={styles.logoIcon}><ArrowLeft size={14} /></div>
             <span className={styles.logoText}>Dashboard</span>
          </div>
          
          <div className={styles.statusHeader}>
            <div className={styles.statusActive}>
              {stats?.status || 'Active Auditing'}
            </div>
            <button 
              className="btn btn-ghost btn-icon" 
              onClick={fetchData} 
              disabled={isRefreshing}
              title="Refresh audits"
            >
              <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center' }}>
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
        </div>
      </header>

      <main className={styles.main}>
        {/* Dashboard Title */}
        <div className={styles.dashboardHeader}>
           <motion.h1 
             className={styles.dashboardTitle}
             initial={{ opacity: 0, x: -20 }}
             animate={{ opacity: 1, x: 0 }}
             transition={{ duration: 0.5 }}
           >
             Agent Alignment Monitor
           </motion.h1>
           <p className={styles.dashboardSub}>
             Real-time Reinforcement Learning performance metrics and trajectory verification.
           </p>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: '2rem' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Stats Grid */}
        <div className={styles.statsGrid}>
           <StatCard 
             label="Agent Precision (Avg Reward)" 
             value={stats?.global_performance.avg_reward.toFixed(3) || '0.000'} 
             icon={Target}
             delay={0}
           />
           <StatCard 
             label="Audit Trajectories" 
             value={stats?.global_performance.total_episodes.toLocaleString() || '0'} 
             icon={Activity}
             delay={0.1}
           />
           <StatCard 
             label="Environment Standard" 
             value={stats?.environment_standard || 'N/A'} 
             icon={ShieldCheck}
             delay={0.2}
           />
           <StatCard 
             label="Last Logic Sync" 
             value={stats?.global_performance.last_run ? new Date(stats.global_performance.last_run).toLocaleTimeString() : 'Never'} 
             icon={Clock}
             delay={0.3}
           />
        </div>

        {/* Audit Table */}
        <motion.div 
          className={styles.auditSection}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
           <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Historical RL Trajectories</h2>
              <div style={{ color: '#6b6b6b', fontSize: '0.8rem' }}>Showing last 30 episodes</div>
           </div>
           
           <div style={{ overflowX: 'auto' }}>
             <table className={styles.auditTable}>
                <thead>
                   <tr>
                      <th>Timestamp</th>
                      <th>Trajectory (Click to expand)</th>
                      <th>Reward</th>
                   </tr>
                </thead>
                <tbody>
                   <AnimatePresence mode='popLayout'>
                    {episodes.map((episode, idx) => {
                       const isExpanded = expandedIndices.includes(idx);
                       
                       return (
                        <motion.tr 
                          key={episode.timestamp + idx} 
                          className={`${styles.auditRow} ${isExpanded ? styles.expandedRow : ''}`}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                           <td className={styles.auditCell} data-label="Timestamp">
                              <div className={styles.cellTimestamp}>
                                 {new Date(episode.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </div>
                           </td>
                           <td 
                             className={`${styles.auditCell} ${styles.clickableCell}`} 
                             data-label="Trajectory"
                             onClick={() => toggleRow(idx)}
                           >
                              <div className={styles.cellQuery}>
                                 <div style={{ fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <ChevronRight 
                                      size={12} 
                                      style={{ 
                                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                                        transition: 'transform 0.2s',
                                        color: '#5e6ad2'
                                      }} 
                                    />
                                    Q: {episode.query}
                                 </div>
                                 <AnimatePresence mode="wait">
                                   {!isExpanded ? (
                                     <motion.div 
                                       key="truncated"
                                       initial={{ opacity: 0 }}
                                       animate={{ opacity: 1 }}
                                       exit={{ opacity: 0 }}
                                       className={styles.truncatedResponse}
                                     >
                                       A: {episode.response.substring(0, 100)}...
                                     </motion.div>
                                   ) : (
                                     <motion.div
                                       key="full"
                                       initial={{ height: 0, opacity: 0 }}
                                       animate={{ height: 'auto', opacity: 1 }}
                                       exit={{ height: 0, opacity: 0 }}
                                       transition={{ duration: 0.3, ease: "easeInOut" }}
                                       className={styles.fullResponse}
                                     >
                                       <div className={styles.responseContainer} style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', marginTop: '0.5rem', borderLeft: '2px solid #5e6ad2' }}>
                                         <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6b6b6b', marginBottom: '0.5rem' }}>Full Agent Response</div>
                                         <div className={styles.markdownContent}>
                                           <ReactMarkdown
                                             remarkPlugins={[remarkGfm, remarkMath]}
                                             rehypePlugins={[rehypeKatex, rehypeRaw]}
                                           >
                                             {preprocessMarkdown(episode.response)}
                                           </ReactMarkdown>
                                         </div>
                                       </div>
                                     </motion.div>
                                   )}
                                 </AnimatePresence>
                              </div>
                           </td>
                           <td className={styles.auditCell} data-label="Reward">
                              <div className={`${styles.cellReward} ${episode.reward >= 0 ? styles.positiveReward : styles.negativeReward}`}>
                                 {episode.reward >= 0 ? '+' : ''}{episode.reward.toFixed(2)}
                              </div>
                           </td>
                        </motion.tr>
                       );
                    })}
                   </AnimatePresence>
                </tbody>
             </table>
             {episodes.length === 0 && !loading && (
               <div style={{ padding: '3rem', textAlign: 'center', color: '#6b6b6b' }}>
                  No RL trajectories found in OpenEnv.
               </div>
             )}
           </div>
        </motion.div>
      </main>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, delay, trend }: { label: string, value: string, icon: any, delay: number, trend?: string }) {
  return (
    <motion.div 
      className={styles.statCard}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <div className={styles.statLabel}>
        <Icon size={12} strokeWidth={2.5} />
        {label}
      </div>
      <div className={styles.statValue}>{value}</div>
      {trend && (
        <div className={`${styles.statTrend} ${trend.startsWith('+') ? styles.trendUp : styles.trendDown}`}>
          {trend.startsWith('+') ? <Zap size={10} fill="currentColor" /> : <ShieldCheck size={10} />}
          {trend} from baseline
        </div>
      )}
    </motion.div>
  );
}

function LogicAuditsSkeleton() {
  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className="skeleton" style={{ width: 140, height: 24 }} />
        <div className="skeleton" style={{ width: 120, height: 24 }} />
      </header>
      <main className={styles.main}>
        <div className={styles.dashboardHeader}>
          <div className="skeleton" style={{ width: 280, height: 32, marginBottom: '0.5rem' }} />
          <div className="skeleton" style={{ width: 400, height: 16 }} />
        </div>
        
        <div className={styles.statsGrid}>
          {[1, 2, 3, 4].map(k => (
            <div key={k} className={`${styles.statCard} skeleton`} style={{ height: 110 }} />
          ))}
        </div>

        <div className={styles.auditSection}>
           <div className={styles.sectionHeader}>
              <div className="skeleton" style={{ width: 220, height: 20 }} />
           </div>
           <div style={{ padding: '1.5rem' }}>
              {[1, 2, 3, 4, 5].map(k => (
                <div key={k} className="skeleton" style={{ width: '100%', height: 48, marginBottom: '0.75rem' }} />
              ))}
           </div>
        </div>
      </main>
    </div>
  );
}

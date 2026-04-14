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
    score: number;
    feedback: string;
  };
  timestamp: string;
}

export default function RLDashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  
  const [stats, setStats] = useState<RLStats | null>(null);
  const [episodes, setEpisodes] = useState<RLEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  if (loading && !isRefreshing) {
    return (
      <div className={styles.root} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={32} color="#5e6ad2" />
      </div>
    );
  }

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
                      <th>Query & Context</th>
                      <th>Reward</th>
                      <th>Critic Review</th>
                   </tr>
                </thead>
                <tbody>
                   <AnimatePresence mode='popLayout'>
                    {episodes.map((episode, idx) => (
                       <motion.tr 
                         key={episode.timestamp + idx} 
                         className={styles.auditRow}
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
                          <td className={styles.auditCell} data-label="Trajectory">
                             <div className={styles.cellQuery}>
                                <div style={{ fontWeight: 600, marginBottom: '4px' }}>Q: {episode.query}</div>
                                <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>A: {episode.response.substring(0, 100)}...</div>
                             </div>
                          </td>
                          <td className={styles.auditCell} data-label="Reward">
                             <div className={`${styles.cellReward} ${episode.reward >= 0 ? styles.positiveReward : styles.negativeReward}`}>
                                {episode.reward >= 0 ? '+' : ''}{episode.reward.toFixed(2)}
                             </div>
                          </td>
                          <td className={styles.auditCell} data-label="Critic">
                             <div className={styles.cellReview}>
                                "{episode.review.feedback}"
                             </div>
                          </td>
                       </motion.tr>
                    ))}
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

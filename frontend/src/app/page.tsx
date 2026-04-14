'use client';

import { motion } from 'framer-motion';
import { BookOpen, Zap, Brain, ChevronRight } from 'lucide-react';
import styles from './login.module.css';
import { signIn } from 'next-auth/react';

const FEATURES = [
  {
    icon: BookOpen,
    label: 'Course-Grounded Answers',
    desc: 'Responses based strictly on your uploaded course materials',
  },
  {
    icon: Zap,
    label: 'Real-time Streaming',
    desc: 'See answers build word-by-word with multi-agent reasoning',
  },
  {
    icon: Brain,
    label: 'Smart Query Routing',
    desc: 'An AI supervisor directs your specific question to the most qualified agent',
  },
];

// const STATS = [
//   { value: '10K+', label: 'Students' },
//   { value: '500+', label: 'Courses' },
//   { value: '98%',  label: 'Satisfaction' },
// ];

export default function LoginPage() {
  const handleGoogleSignIn = () => {
    signIn('google', { callbackUrl: '/dashboard' });
  };

  return (
    <>
      <main className={styles.root}>
        {/* ── Left panel ── */}
        <motion.div
          className={styles.leftPanel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          {/* Logo */}
          <div className={styles.logoRow}>
            <div className={styles.logoIcon}>
              <BookOpen size={16} strokeWidth={2.5} />
            </div>
            <span className={styles.logoText}>EduVerse</span>
          </div>

          {/* Hero content */}
          <div className={styles.heroContent}>
            <motion.h1
              className={styles.heroTitle}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1, duration: 0.5, ease: 'easeOut' }}
            >
              Your classroom,<br />now with an AI tutor.
            </motion.h1>

            <motion.p
              className={styles.heroSub}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.18, duration: 0.5, ease: 'easeOut' }}
            >
              Seamlessly sync with Google Classroom to transform your static 
              lectures, assignments, and syllabus into an intelligent, 
              always-on AI study companion.
            </motion.p>

            {/* Feature list */}
            <motion.div
              className={styles.featureList}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.28, duration: 0.5 }}
            >
              {FEATURES.map(({ icon: Icon, label, desc }, i) => (
                <motion.div
                  key={label}
                  className={styles.featureRow}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.32 + i * 0.07, duration: 0.4 }}
                >
                  <div className={styles.featureIconWrap}>
                    <Icon size={14} strokeWidth={2} />
                  </div>
                  <div>
                    <div className={styles.featureLabel}>{label}</div>
                    <div className={styles.featureDesc}>{desc}</div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </div>

          {/* Bottom stats */}
          {/* <div className={styles.statsRow}>
            {STATS.map(({ value, label }) => (
              <div key={label} className={styles.statItem}>
                <span className={styles.statValue}>{value}</span>
                <span className={styles.statLabel}>{label}</span>
              </div>
            ))}
          </div> */}
        </motion.div>

        {/* ── Right panel ── */}
        <motion.div
          className={styles.rightPanel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.5, ease: 'easeOut' }}
        >
          <div className={styles.card}>
            {/* Header */}
            <div>
              <div className={styles.cardLabel}>Get started</div>
              <h2 className={styles.cardTitle}>Sign in to EduVerse</h2>
              <p className={styles.cardSub}>Access your courses and AI tutor</p>
            </div>

            <div className={styles.cardDivider} />

            {/* Google sign-in */}
            <button
              id="google-signin-btn"
              className={styles.googleBtn}
              onClick={handleGoogleSignIn}
            >
              <GoogleIcon />
              <span className={styles.googleBtnLabel}>Continue with Google</span>
              <ChevronRight size={15} className={styles.googleBtnChevron} />
            </button>

            {/* Privacy */}
            <p className={styles.privacyNote}>
              By signing in, you allow EduVerse to read your Google Classroom
              data to power your AI tutor.{' '}
              <a href="#">Learn more</a>
            </p>
          </div>
        </motion.div>
      </main>
    </>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
      <path d="M17.64 9.20455C17.64 8.56636 17.5827 7.95273 17.4764 7.36364H9V10.845H13.8436C13.635 11.97 13.0009 12.9232 12.0477 13.5614V15.8195H14.9564C16.6582 14.2527 17.64 11.9455 17.64 9.20455Z" fill="#4285F4"/>
      <path d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5614C11.2418 14.1014 10.2109 14.4205 9 14.4205C6.65591 14.4205 4.67182 12.8373 3.96409 10.71H0.957275V13.0418C2.43818 15.9832 5.48182 18 9 18Z" fill="#34A853"/>
      <path d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40682 3.78409 7.83 3.96409 7.29V4.95818H0.957275C0.347727 6.17318 0 7.54773 0 9C0 10.4523 0.347727 11.8268 0.957275 13.0418L3.96409 10.71Z" fill="#FBBC05"/>
      <path d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65591 3.57955 9 3.57955Z" fill="#EA4335"/>
    </svg>
  );
}

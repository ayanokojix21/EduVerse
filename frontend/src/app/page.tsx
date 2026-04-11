'use client';

import { motion } from 'framer-motion';
import { BookOpen, Sparkles, Brain, Zap, Users, ChevronRight } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import styles from './login.module.css';

import { signIn } from 'next-auth/react';

const FEATURES = [
  { icon: Brain, label: 'AI-Powered Tutoring', desc: 'Personalized answers grounded in your course materials' },
  { icon: Zap,   label: 'Instant Responses',   desc: 'Real-time streaming with multi-agent reasoning' },
  { icon: Users, label: 'HiveMind Tutors',      desc: 'Two AI tutors debate the best way to explain concepts' },
];

export default function LoginPage() {
  const handleGoogleSignIn = () => {
    signIn('google', { callbackUrl: '/dashboard' });
  };

  return (
    <>
      {/* Animated mesh background */}
      <div className="mesh-bg" aria-hidden />

      {/* Floating theme toggle */}
      <ThemeToggle floating />

      <main className={styles.root}>
        {/* ── Left hero panel ── */}
        <motion.div
          className={styles.hero}
          initial={{ opacity: 0, x: -40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Logo */}
          <div className={styles.logoRow}>
            <div className={styles.logoIcon}>
              <BookOpen size={26} />
            </div>
            <span className={`${styles.logoText} font-display`}>EduVerse</span>
          </div>

          <motion.h1
            className={`${styles.heroTitle} font-display`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            Learn smarter with{' '}
            <span className="gradient-text">AI tutoring</span>{' '}
            built for your classroom
          </motion.h1>

          <motion.p
            className={styles.heroSub}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.6 }}
          >
            EduVerse connects to your Google Classroom and turns every lecture, 
            assignment, and resource into an interactive AI tutor — available 24/7.
          </motion.p>

          {/* Feature chips */}
          <motion.div
            className={styles.features}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.6 }}
          >
            {FEATURES.map(({ icon: Icon, label, desc }, i) => (
              <motion.div
                key={label}
                className={styles.featureChip}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.45 + i * 0.1, duration: 0.5 }}
              >
                <div className={styles.featureIcon}>
                  <Icon size={16} />
                </div>
                <div>
                  <div className={styles.featureLabel}>{label}</div>
                  <div className={styles.featureDesc}>{desc}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>

          {/* Ambient glow orbs */}
          <div className={styles.orb1} aria-hidden />
          <div className={styles.orb2} aria-hidden />
        </motion.div>

        {/* ── Right sign-in card ── */}
        <motion.div
          className={styles.cardWrap}
          initial={{ opacity: 0, y: 40, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className={`${styles.card} glass-card-flat`}>
            {/* Card header */}
            <div className={styles.cardHeader}>
              <div className={styles.sparkleRow}>
                <Sparkles size={14} style={{ color: 'var(--accent)' }} />
                <span className={styles.sparkleText}>AI-Powered Learning</span>
              </div>
              <h2 className={`${styles.cardTitle} font-display`}>Welcome back</h2>
              <p className={styles.cardSub}>
                Sign in with Google to access your personalized AI tutor and course materials.
              </p>
            </div>

            {/* Divider */}
            <div className="divider" />

            {/* Google Sign-in button */}
            <motion.button
              id="google-signin-btn"
              className={styles.googleBtn}
              onClick={handleGoogleSignIn}
              whileHover={{ scale: 1.02, y: -2 }}
              whileTap={{ scale: 0.97 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            >
              <GoogleIcon />
              <span>Continue with Google</span>
              <ChevronRight size={16} style={{ marginLeft: 'auto', opacity: 0.6 }} />
            </motion.button>

            {/* Privacy note */}
            <p className={styles.privacyNote}>
              By continuing, you agree to EduVerse accessing your Google Classroom 
              courses and materials to power your AI tutor.{' '}
              <a href="#" style={{ color: 'var(--primary-light)' }}>Learn more</a>
            </p>

            {/* Stats row */}
            <div className="divider" />
            <div className={styles.statsRow}>
              {[
                { value: '10K+', label: 'Students' },
                { value: '500+', label: 'Courses' },
                { value: '98%', label: 'Satisfaction' },
              ].map(({ value, label }) => (
                <div key={label} className={styles.statItem}>
                  <div className={styles.statValue}>{value}</div>
                  <div className={styles.statLabel}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </main>
    </>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.20455C17.64 8.56636 17.5827 7.95273 17.4764 7.36364H9V10.845H13.8436C13.635 11.97 13.0009 12.9232 12.0477 13.5614V15.8195H14.9564C16.6582 14.2527 17.64 11.9455 17.64 9.20455Z" fill="#4285F4"/>
      <path d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5614C11.2418 14.1014 10.2109 14.4205 9 14.4205C6.65591 14.4205 4.67182 12.8373 3.96409 10.71H0.957275V13.0418C2.43818 15.9832 5.48182 18 9 18Z" fill="#34A853"/>
      <path d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40682 3.78409 7.83 3.96409 7.29V4.95818H0.957275C0.347727 6.17318 0 7.54773 0 9C0 10.4523 0.347727 11.8268 0.957275 13.0418L3.96409 10.71Z" fill="#FBBC05"/>
      <path d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65591 3.57955 9 3.57955Z" fill="#EA4335"/>
    </svg>
  );
}

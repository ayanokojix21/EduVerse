"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ArrowUpRight, BookOpen, Brain, Shield, Zap, Network, MessageSquare, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/Button";

const CampusJourney = dynamic(
  () => import("@/components/three/CampusJourney").then(m => ({ default: m.CampusJourney })),
  { ssr: false }
);

// Returns 0-1 opacity for a scroll range, with fade in/out margins
function op(p: number, s: number, e: number, fade = 0.035): number {
  if (p < s - fade || p > e + fade) return 0;
  if (p < s) return (p - (s - fade)) / fade;
  if (p > e) return 1 - (p - e) / fade;
  return 1;
}

const FEATURES = [
  { icon: Brain,         title: "Socratic AI Tutor",   desc: "Reasons through your course materials before answering. Every response is grounded, cited, and curriculum-aligned." },
  { icon: Shield,        title: "Zero Hallucination",  desc: "All answers are grounded in your actual classroom documents with inline PDF citations." },
  { icon: Zap,           title: "Real-time Streaming", desc: "Watch the AI think token-by-token. Live agent reasoning, confidence scores, and execution traces." },
  { icon: Network,       title: "Knowledge Universe",  desc: "Your mastery mapped as a force-directed D3 graph. See topic strength and learning gaps at a glance." },
  { icon: MessageSquare, title: "Human-in-the-Loop",   desc: "When confidence is low the AI pauses and asks you — search the web or stay course-grounded." },
  { icon: BarChart3,     title: "RLAIF Training",      desc: "Your feedback trains a shadow model via reinforcement learning. EduVerse gets smarter every session." },
];

export default function Page() {
  const router = useRouter();
  const { loginWithGoogle, loginAsGuest, isAuthenticated, isLoading } = useAuth();
  const [progress, setProgress] = useState(0);
  const [guest,    setGuest]    = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    const fn = () => {
      const pct = scrollY / Math.max(document.documentElement.scrollHeight - innerHeight, 1);
      setProgress(pct);
      setScrolled(scrollY > 60);
    };
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  const doGuest = async () => {
    setGuest(true);
    try {
      await loginAsGuest();
      router.push("/dashboard");
    } catch {
      setGuest(false);
    }
  };

  const GoogleIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );

  return (
    <>
      {/* ── 3D Journey canvas (fixed, behind everything) ──────────────── */}
      <CampusJourney />

      {/* ── Scroll container — sets total scroll height ───────────────── */}
      <div style={{ height: "700vh", position: "relative", zIndex: 1, pointerEvents: "none" }} />

      {/* ── NAV (always fixed) ───────────────────────────────────────────── */}
      <nav
        className={`
          fixed top-0 left-0 right-0 z-[200]
          flex items-center justify-between
          px-10 py-4
          transition-all duration-300
          pointer-events-auto
          ${scrolled ? "nav-glass" : "nav-transparent"}
        `}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-[var(--color-primary)] flex items-center justify-center">
            <BookOpen size={16} className="text-[var(--color-bg)]" />
          </div>
          <span className="font-extrabold text-[17px] tracking-tight text-[var(--color-text-main)]">
            EduVerse
          </span>
        </div>
        <Button onClick={() => loginWithGoogle()} variant="primary">
          Enter Metaverse
        </Button>
      </nav>

      {/* ═══════════════════════════════════════════════════════════════════
          ALL OVERLAYS: fixed, pointer-events controlled by opacity
      ═══════════════════════════════════════════════════════════════════ */}

      {/* ── HERO (p 0 → 0.22) ────────────────────────────────────────────── */}
      <div
        className="fixed bottom-[15vh] left-[15%] z-[100] max-w-[480px] lg:max-w-[540px]"
        style={{
          opacity: op(progress, 0, 0.22),
          transform: `translateY(${(1 - op(progress, 0, 0.22)) * 30}px)`,
          pointerEvents: op(progress, 0, 0.22) > 0.1 ? "auto" : "none",
        }}
      >
        <div className="font-mono text-[11px] text-[var(--color-text-muted)] tracking-widest uppercase mb-4 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-main)] animate-pulse" />
          Next-Gen Learning Metaverse
        </div>
        <h1 className="text-[clamp(2.5rem,6vw,4.5rem)] font-extrabold leading-[1.06] tracking-tight mb-5 text-[var(--color-text-main)]">
          Step Into The <span className="text-[var(--color-text-dim)]">Future of Learning.</span>
        </h1>
        <p className="text-base text-[var(--color-text-muted)] leading-[1.75] mb-9 max-w-[500px]">
          Immersive 3D worlds, AI tutors, and gamified courses. EduVerse grounds every answer in your real curriculum — zero hallucinations.
        </p>
        <div className="flex gap-3 flex-wrap">
          <Button
            id="cta-google"
            onClick={() => loginWithGoogle()}
            variant="primary"
            leftIcon={<GoogleIcon />}
          >
            Sign in with Google
          </Button>
          <Button
            id="cta-guest"
            onClick={doGuest}
            variant="ghost"
            loading={guest}
            leftIcon={!guest && <ArrowUpRight size={15} />}
          >
            Continue as Guest
          </Button>
        </div>
        <div className="mt-6 flex items-center gap-2 opacity-40">
          <div className="w-[1px] h-9 bg-gradient-to-b from-[var(--color-text-main)] to-transparent" />
          <span className="font-mono text-[10px] text-[var(--color-text-main)] uppercase tracking-wider">Scroll to enter</span>
        </div>
      </div>

      {/* ── ENTERING caption (p 0.22 → 0.38) ───────────────────────────── */}
      <div
        className="fixed top-1/2 left-1/2 z-[100] text-center pointer-events-none"
        style={{
          transform: `translate(-50%, -50%) scale(${.85 + op(progress, .22, .38) * .15})`,
          opacity: op(progress, .22, .38),
        }}
      >
        <div className="font-mono text-[12px] text-[var(--color-text-dim)] uppercase mb-3 tracking-[0.25em]">
          // ENTERING KNOWLEDGE CORE
        </div>
        <div className="text-[clamp(1.6rem,4vw,3rem)] font-extrabold tracking-tight text-[var(--color-text-main)]">
          The Library Awaits.
        </div>
      </div>

      {/* ── LIBRARY FEATURES (p 0.38 → 0.72) ─────── */}
      {/* Left panel */}
      <div
        className="fixed top-1/2 left-[15%] z-[100] max-w-[320px] lg:max-w-[380px] pointer-events-none"
        style={{
          transform: `translateY(-50%) translateX(${(1 - op(progress, .38, .72)) * -40}px)`,
          opacity: op(progress, .38, .72),
        }}
      >
        <div className="glass-panel rounded-xl p-7 mb-4">
          <div className="font-mono text-[10px] text-[var(--color-text-dim)] mb-2.5">// 01 · 02 · 03</div>
          <h2 className="text-[1.5rem] font-extrabold tracking-tight mb-4 text-[var(--color-text-main)]">
            Core Capabilities.
          </h2>
          {FEATURES.slice(0, 3).map(f => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="flex gap-3 mb-3.5">
                <div className="w-8 h-8 shrink-0 border border-[var(--color-border)] bg-[var(--color-bg)] flex items-center justify-center rounded-md">
                  <Icon size={14} className="text-[var(--color-text-main)]" />
                </div>
                <div>
                  <div className="text-[13px] font-bold text-[var(--color-text-main)] mb-1">{f.title}</div>
                  <div className="text-[11px] text-[var(--color-text-muted)] leading-[1.6]">{f.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel */}
      <div
        className="fixed top-1/2 right-[15%] z-[100] max-w-[320px] lg:max-w-[380px] pointer-events-none"
        style={{
          transform: `translateY(-50%) translateX(${(1 - op(progress, .45, .75)) * 40}px)`,
          opacity: op(progress, .45, .75),
        }}
      >
        <div className="glass-panel rounded-xl p-7">
          <div className="font-mono text-[10px] text-[var(--color-text-dim)] mb-2.5">// 04 · 05 · 06</div>
          <h2 className="text-[1.5rem] font-extrabold tracking-tight mb-4 text-[var(--color-text-main)]">
            Intelligence Layer.
          </h2>
          {FEATURES.slice(3).map(f => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="flex gap-3 mb-3.5">
                <div className="w-8 h-8 shrink-0 border border-[var(--color-border)] bg-[var(--color-bg)] flex items-center justify-center rounded-md">
                  <Icon size={14} className="text-[var(--color-text-main)]" />
                </div>
                <div>
                  <div className="text-[13px] font-bold text-[var(--color-text-main)] mb-1">{f.title}</div>
                  <div className="text-[11px] text-[var(--color-text-muted)] leading-[1.6]">{f.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── MISSION statement (p 0.62 → 0.80) ──────────────────────────── */}
      <div
        className="fixed bottom-[10vh] left-1/2 z-[100] text-center max-w-[620px] pointer-events-none"
        style={{
          transform: `translateX(-50%) translateY(${(1 - op(progress, .62, .80)) * 30}px)`,
          opacity: op(progress, .62, .80),
        }}
      >
        <div className="font-mono text-[11px] text-[var(--color-text-dim)] uppercase tracking-widest mb-3">// Our Mission</div>
        <p className="text-[clamp(1.1rem,2.5vw,1.5rem)] font-bold leading-[1.5] tracking-tight text-[var(--color-text-main)]">
          Learning should feel like exploring a world — not sitting in a lecture.{" "}
          <span className="text-[var(--color-text-dim)]">EduVerse makes it so.</span>
        </p>
      </div>

      {/* ── HUB / CTA terminal (p 0.80 → 1.0) ──────────────────────────── */}
      <div
        className="fixed top-1/2 left-1/2 z-[100] text-center max-w-[680px]"
        style={{
          transform: `translate(-50%, -50%) scale(${.88 + op(progress, .80, 1) * .12})`,
          opacity: op(progress, .80, 1),
          pointerEvents: op(progress, .80, 1) > 0.1 ? "auto" : "none",
        }}
      >
        <div className="glass-panel rounded-xl px-11 py-12">
          <div className="font-mono text-[11px] text-[var(--color-text-dim)] uppercase mb-4 tracking-[0.2em]">// DIGITAL HUB · CENTRAL TERMINAL</div>
          <h2 className="text-[clamp(2rem,4.5vw,3.2rem)] font-extrabold tracking-tight leading-[1.1] mb-5 text-[var(--color-text-main)]">
            Ready to enter the <span className="text-[var(--color-text-dim)]">metaverse?</span>
          </h2>
          <p className="text-[15px] text-[var(--color-text-muted)] leading-[1.7] mb-9 max-w-[480px] mx-auto">
            Connect Google Classroom in 30 seconds. Zero-hallucination AI. Curriculum-grounded. Always.
          </p>
          <div className="flex gap-3 justify-center flex-wrap mb-8">
            <Button
              onClick={() => loginWithGoogle()}
              variant="primary"
              leftIcon={<GoogleIcon />}
            >
              Start Learning Free
            </Button>
            <Button
              onClick={doGuest}
              variant="ghost"
              loading={guest}
              leftIcon={!guest && <ArrowUpRight size={16} />}
            >
              Guest Access
            </Button>
          </div>
          {/* Footer links row */}
          <div className="border-t border-[var(--color-border)] pt-6 flex justify-center flex-wrap gap-x-6 gap-y-2">
            {["Discord", "Twitter", "GitHub", "Privacy", "Terms", "About"].map(l => (
              <span key={l} className="font-mono text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-text-main)] transition-colors cursor-pointer">
                {l}
              </span>
            ))}
          </div>
          <div className="mt-3 font-mono text-[10px]" style={{ color: 'rgba(83,100,113,0.5)' }}>
            © 2026 EduVerse · LangGraph · Gemma 4 · Next.js 16
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div
        className="fixed bottom-0 left-0 z-[300] pointer-events-none h-0.5 bg-[var(--color-text-main)] transition-all duration-100"
        style={{ width: `${progress * 100}%` }}
      />
    </>
  );
}

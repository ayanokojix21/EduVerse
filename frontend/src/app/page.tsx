"use client";
import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ArrowUpRight, BookOpen, Brain, Shield, Zap, Network, MessageSquare, BarChart3 } from "lucide-react";

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

const mono: React.CSSProperties = { fontFamily: "'Courier New',monospace", letterSpacing: "0.1em" };

export default function Page() {
  const router = useRouter();
  const { loginWithGoogle, loginAsGuest, isAuthenticated, isLoading } = useAuth();
  const [progress, setProgress] = useState(0);
  const [guest,    setGuest]    = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => { if (!isLoading && isAuthenticated) router.replace("/dashboard"); }, [isAuthenticated, isLoading, router]);

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
    try { await loginAsGuest(); router.push("/dashboard"); } catch { setGuest(false); }
  };

  const glass: React.CSSProperties = {
    background: "rgba(3,7,18,0.75)",
    backdropFilter: "blur(24px)",
    border: "1px solid rgba(0,212,255,0.2)",
    borderRadius: 12,
  };

  const cyanText: React.CSSProperties = {
    background: "linear-gradient(90deg,#00d4ff,#8b5cf6)",
    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
  };

  return (
    <>
      {/* Google Font */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        html{scroll-behavior:auto}
        body{font-family:'Space Grotesk',sans-serif;background:#030712;color:#f0f6ff;overflow-x:hidden}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-thumb{background:rgba(0,212,255,.3);border-radius:2px}
      `}</style>

      {/* ── 3D Journey canvas (fixed, behind everything) ──────────────── */}
      <CampusJourney />

      {/* ── Scroll container — sets total scroll height ───────────────── */}
      <div style={{ height: "700vh", position: "relative", zIndex: 1, pointerEvents: "none" }} />

      {/* ── NAV (always fixed) ───────────────────────────────────────────── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 200,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "16px 40px",
        background: scrolled ? "rgba(3,7,18,0.85)" : "transparent",
        backdropFilter: scrolled ? "blur(20px)" : "none",
        borderBottom: scrolled ? "1px solid rgba(0,212,255,0.1)" : "none",
        transition: "all .35s", pointerEvents: "auto",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg,#00d4ff,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BookOpen size={15} color="#fff" />
          </div>
          <span style={{ fontWeight: 800, fontSize: 17, ...cyanText }}>EduVerse</span>
        </div>
        <button onClick={() => loginWithGoogle()} style={{
          padding: "9px 24px", borderRadius: 999,
          background: "linear-gradient(135deg,#00d4ff,#8b5cf6)", border: "none",
          color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer",
          fontFamily: "'Space Grotesk',sans-serif",
          boxShadow: "0 0 20px rgba(0,212,255,0.35)",
        }}>Enter Metaverse</button>
      </nav>

      {/* ═══════════════════════════════════════════════════════════════════
          ALL OVERLAYS: fixed, pointer-events controlled by opacity
      ═══════════════════════════════════════════════════════════════════ */}

      {/* ── HERO (p 0 → 0.22) ────────────────────────────────────────────── */}
      <div style={{
        position: "fixed", bottom: "8vh", left: "6vw", zIndex: 100,
        maxWidth: 640,
        opacity: op(progress, 0, 0.22),
        transform: `translateY(${(1 - op(progress, 0, 0.22)) * 30}px)`,
        transition: "none", pointerEvents: op(progress, 0, 0.22) > 0.1 ? "auto" : "none",
      }}>
        <div style={{ ...mono, fontSize: 11, color: "rgba(0,212,255,0.8)", textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00d4ff", display: "inline-block", animation: "blink 2s ease-in-out infinite" }} />
          Next-Gen Learning Metaverse
        </div>
        <h1 style={{ fontSize: "clamp(2.5rem,6vw,4.5rem)", fontWeight: 800, lineHeight: 1.06, letterSpacing: "-0.04em", marginBottom: 20 }}>
          Step Into The{" "}
          <span style={cyanText}>Future of Learning.</span>
        </h1>
        <p style={{ fontSize: 16, color: "rgba(200,220,255,0.6)", lineHeight: 1.75, marginBottom: 36, maxWidth: 500 }}>
          Immersive 3D worlds, AI tutors, and gamified courses. EduVerse grounds every answer in your real curriculum — zero hallucinations.
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button id="cta-google" onClick={() => loginWithGoogle()} style={{
            display: "inline-flex", alignItems: "center", gap: 10, padding: "14px 30px", borderRadius: 999,
            background: "linear-gradient(135deg,#00d4ff,#8b5cf6)", border: "none", color: "#fff",
            fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif",
            boxShadow: "0 0 40px rgba(0,212,255,0.45)",
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
            Sign in with Google
          </button>
          <button id="cta-guest" onClick={doGuest} disabled={guest} style={{
            display: "inline-flex", alignItems: "center", gap: 8, padding: "14px 30px", borderRadius: 999,
            background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.18)",
            backdropFilter: "blur(10px)", color: "rgba(200,220,255,0.85)",
            fontSize: 14, fontWeight: 600, cursor: guest ? "not-allowed" : "pointer", fontFamily: "'Space Grotesk',sans-serif",
          }}>
            {guest ? <span style={{ width: 13, height: 13, border: "2px solid rgba(200,220,255,0.4)", borderTopColor: "#00d4ff", borderRadius: "50%", display: "inline-block", animation: "spin .8s linear infinite" }} /> : <ArrowUpRight size={15} />}
            Continue as Guest
          </button>
        </div>
        <div style={{ marginTop: 24, display: "flex", alignItems: "center", gap: 8, opacity: 0.4 }}>
          <div style={{ width: 1, height: 36, background: "linear-gradient(to bottom,#00d4ff,transparent)" }} />
          <span style={{ ...mono, fontSize: 10, color: "#00d4ff", textTransform: "uppercase" }}>Scroll to enter</span>
        </div>
      </div>

      {/* ── ENTERING caption (p 0.22 → 0.38) ───────────────────────────── */}
      <div style={{
        position: "fixed", top: "50%", left: "50%", zIndex: 100,
        transform: `translate(-50%, -50%) scale(${.85 + op(progress, .22, .38) * .15})`,
        opacity: op(progress, .22, .38),
        textAlign: "center", pointerEvents: "none",
      }}>
        <div style={{ ...mono, fontSize: 12, color: "#00d4ff", textTransform: "uppercase", marginBottom: 12, letterSpacing: "0.25em" }}>
          // ENTERING KNOWLEDGE CORE
        </div>
        <div style={{ fontSize: "clamp(1.6rem,4vw,3rem)", fontWeight: 800, letterSpacing: "-0.03em", ...cyanText }}>
          The Library Awaits.
        </div>
      </div>

      {/* ── LIBRARY FEATURES: holographic panels (p 0.38 → 0.72) ─────── */}
      {/* Left panel */}
      <div style={{
        position: "fixed", top: "50%", left: "5vw", zIndex: 100,
        transform: `translateY(-50%) translateX(${(1 - op(progress, .38, .72)) * -40}px)`,
        opacity: op(progress, .38, .72),
        maxWidth: 340, pointerEvents: "none",
      }}>
        <div style={{ ...glass, padding: "28px 24px", marginBottom: 16 }}>
          <div style={{ ...mono, fontSize: 10, color: "rgba(0,212,255,0.6)", marginBottom: 10 }}>// 01 · 02 · 03</div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.025em", marginBottom: 16 }}>
            Core <span style={cyanText}>Capabilities.</span>
          </h2>
          {FEATURES.slice(0, 3).map(f => {
            const Icon = f.icon;
            return (
              <div key={f.title} style={{ display: "flex", gap: 12, marginBottom: 14 }}>
                <div style={{ width: 32, height: 32, flexShrink: 0, border: "1px solid rgba(0,212,255,0.25)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 6 }}>
                  <Icon size={14} color="#00d4ff" />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 3 }}>{f.title}</div>
                  <div style={{ fontSize: 11, color: "rgba(200,220,255,0.45)", lineHeight: 1.6 }}>{f.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel */}
      <div style={{
        position: "fixed", top: "50%", right: "5vw", zIndex: 100,
        transform: `translateY(-50%) translateX(${(1 - op(progress, .45, .75)) * 40}px)`,
        opacity: op(progress, .45, .75),
        maxWidth: 340, pointerEvents: "none",
      }}>
        <div style={{ ...glass, padding: "28px 24px" }}>
          <div style={{ ...mono, fontSize: 10, color: "rgba(139,92,246,0.6)", marginBottom: 10 }}>// 04 · 05 · 06</div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.025em", marginBottom: 16 }}>
            Intelligence <span style={{ background: "linear-gradient(90deg,#8b5cf6,#ec4899)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Layer.</span>
          </h2>
          {FEATURES.slice(3).map(f => {
            const Icon = f.icon;
            return (
              <div key={f.title} style={{ display: "flex", gap: 12, marginBottom: 14 }}>
                <div style={{ width: 32, height: 32, flexShrink: 0, border: "1px solid rgba(139,92,246,0.25)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 6 }}>
                  <Icon size={14} color="#8b5cf6" />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 3 }}>{f.title}</div>
                  <div style={{ fontSize: 11, color: "rgba(200,220,255,0.45)", lineHeight: 1.6 }}>{f.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── MISSION statement (p 0.62 → 0.80) ──────────────────────────── */}
      <div style={{
        position: "fixed", bottom: "10vh", left: "50%", zIndex: 100,
        transform: `translateX(-50%) translateY(${(1 - op(progress, .62, .80)) * 30}px)`,
        opacity: op(progress, .62, .80),
        textAlign: "center", maxWidth: 620, pointerEvents: "none",
      }}>
        <div style={{ ...mono, fontSize: 11, color: "rgba(0,212,255,0.5)", textTransform: "uppercase", marginBottom: 12 }}>// Our Mission</div>
        <p style={{ fontSize: "clamp(1.1rem,2.5vw,1.5rem)", fontWeight: 700, lineHeight: 1.5, letterSpacing: "-0.02em", color: "rgba(200,220,255,0.85)" }}>
          Learning should feel like exploring a world — not sitting in a lecture.{" "}
          <span style={cyanText}>EduVerse makes it so.</span>
        </p>
      </div>

      {/* ── HUB / CTA terminal (p 0.80 → 1.0) ──────────────────────────── */}
      <div style={{
        position: "fixed", top: "50%", left: "50%", zIndex: 100,
        transform: `translate(-50%, -50%) scale(${.88 + op(progress, .80, 1) * .12})`,
        opacity: op(progress, .80, 1),
        textAlign: "center", maxWidth: 680,
        pointerEvents: op(progress, .80, 1) > 0.1 ? "auto" : "none",
      }}>
        <div style={{ ...glass, padding: "48px 44px", border: "1px solid rgba(0,212,255,0.3)" }}>
          <div style={{ ...mono, fontSize: 11, color: "rgba(0,212,255,0.6)", textTransform: "uppercase", marginBottom: 16, letterSpacing: "0.2em" }}>// DIGITAL HUB · CENTRAL TERMINAL</div>
          <h2 style={{ fontSize: "clamp(2rem,4.5vw,3.2rem)", fontWeight: 800, letterSpacing: "-0.035em", lineHeight: 1.1, marginBottom: 18 }}>
            Ready to enter the{" "}
            <span style={cyanText}>metaverse?</span>
          </h2>
          <p style={{ fontSize: 15, color: "rgba(200,220,255,0.55)", lineHeight: 1.7, marginBottom: 36, maxWidth: 480, margin: "0 auto 36px" }}>
            Connect Google Classroom in 30 seconds. Zero-hallucination AI. Curriculum-grounded. Always.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap", marginBottom: 32 }}>
            <button onClick={() => loginWithGoogle()} style={{
              display: "inline-flex", alignItems: "center", gap: 10, padding: "15px 34px", borderRadius: 999,
              background: "linear-gradient(135deg,#00d4ff,#8b5cf6)", border: "none", color: "#fff",
              fontSize: 15, fontWeight: 700, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif",
              boxShadow: "0 0 50px rgba(0,212,255,0.5)",
            }}>
              <svg width="15" height="15" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
              Start Learning Free
            </button>
            <button onClick={doGuest} style={{
              display: "inline-flex", alignItems: "center", gap: 8, padding: "15px 34px", borderRadius: 999,
              background: "transparent", border: "1px solid rgba(0,212,255,0.35)", color: "#00d4ff",
              fontSize: 15, fontWeight: 600, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif",
            }}>
              <ArrowUpRight size={16} /> Guest Access
            </button>
          </div>
          {/* Footer links row */}
          <div style={{ borderTop: "1px solid rgba(0,212,255,0.1)", paddingTop: 22, display: "flex", justifyContent: "center", flexWrap: "wrap", gap: "8px 24px" }}>
            {["Discord", "Twitter", "GitHub", "Privacy", "Terms", "About"].map(l => (
              <span key={l} style={{ ...mono, fontSize: 11, color: "rgba(200,220,255,0.3)", cursor: "pointer" }}
                onMouseEnter={e => ((e.target as HTMLElement).style.color = "#00d4ff")}
                onMouseLeave={e => ((e.target as HTMLElement).style.color = "rgba(200,220,255,0.3)")}>
                {l}
              </span>
            ))}
          </div>
          <div style={{ marginTop: 12, ...mono, fontSize: 10, color: "rgba(200,220,255,0.18)" }}>
            © 2026 EduVerse · LangGraph · Gemma 4 · Next.js 15
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        position: "fixed", bottom: 0, left: 0, zIndex: 300, pointerEvents: "none",
        width: `${progress * 100}%`, height: 2,
        background: "linear-gradient(90deg,#00d4ff,#8b5cf6)",
        boxShadow: "0 0 8px rgba(0,212,255,0.8)",
        transition: "width .1s",
      }} />
    </>
  );
}

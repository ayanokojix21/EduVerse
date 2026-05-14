"use client";

// ─────────────────────────────────────────────────────────────────────────────
// AuthGuard — Client-side auth gate for the (app) route group.
// Redirects to / if no valid JWT is found. Runs alongside middleware for
// full SPA coverage (middleware handles direct navigation, AuthGuard
// handles client-side routing).
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

interface AuthGuardProps {
  children: React.ReactNode;
  /** If true, also check for admin role */
  requireAdmin?: boolean;
}

export function AuthGuard({ children, requireAdmin = false }: AuthGuardProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      router.replace("/");
      return;
    }

    if (requireAdmin && user?.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [isLoading, isAuthenticated, requireAdmin, user?.role, router]);

  // Show nothing while checking auth
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-dvh bg-black">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#2F3336] border-t-[#EFF3F4] rounded-full animate-spin" />
          <span className="text-[13px] text-[#71767B]">Loading…</span>
        </div>
      </div>
    );
  }

  // Not authenticated — show nothing (redirect is in progress)
  if (!isAuthenticated) return null;

  // Admin check failed — show nothing (redirect is in progress)
  if (requireAdmin && user?.role !== "admin") return null;

  return <>{children}</>;
}

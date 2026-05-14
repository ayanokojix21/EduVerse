import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/components/layout/AuthGuard";

// ─────────────────────────────────────────────────────────────────────────────
// Authenticated App Shell Layout
// Wraps all routes under (app)/ with:
//   1. AuthGuard — redirects unauthenticated users to /
//   2. AppShell  — sidebar + main content layout
// ─────────────────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: {
    default: "EduVerse",
    template: "%s · EduVerse",
  },
};

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}

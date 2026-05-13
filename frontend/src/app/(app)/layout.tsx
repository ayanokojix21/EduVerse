import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";

// ─────────────────────────────────────────────────────────────────────────────
// Authenticated App Shell Layout
// Wraps all routes under (app)/ with the sidebar + main content layout.
// Auth guard is intentionally lightweight here — redirect logic lives in
// each page or a middleware.ts if needed later.
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
  return <AppShell>{children}</AppShell>;
}

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

// ─────────────────────────────────────────────────────────────────────────────
// Font
// ─────────────────────────────────────────────────────────────────────────────

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  weight: ["300", "400", "500", "600", "700", "800"],
});

// ─────────────────────────────────────────────────────────────────────────────
// Metadata
// ─────────────────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: {
    default: "EduVerse — AI-Powered Learning",
    template: "%s · EduVerse",
  },
  description:
    "EduVerse is an intelligent AI tutor that learns from your course materials, answers questions with grounded citations, and adapts to your mastery over time.",
  keywords: ["AI tutor", "education", "Google Classroom", "learning", "EduVerse"],
  authors: [{ name: "EduVerse Team" }],
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    title: "EduVerse — AI-Powered Learning",
    description: "Your AI tutor that knows your curriculum inside out.",
    siteName: "EduVerse",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#000000",
};

// ─────────────────────────────────────────────────────────────────────────────
// Root Layout
// ─────────────────────────────────────────────────────────────────────────────

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Preconnect to Google Fonts CDN */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* KaTeX CSS for math rendering */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css"
          crossOrigin="anonymous"
        />
      </head>
      <body className="bg-black text-[#E7E9EA] antialiased min-h-dvh">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

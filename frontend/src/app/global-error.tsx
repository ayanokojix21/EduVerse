"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Global Error Boundary — Root-level error handler.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[EduVerse Global Error]", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          backgroundColor: "#000",
          color: "#E7E9EA",
          fontFamily: "Inter, -apple-system, sans-serif",
          margin: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100dvh",
        }}
      >
        <div style={{ textAlign: "center", maxWidth: 400, padding: 24 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              backgroundColor: "rgba(244,33,46,0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 20px",
            }}
          >
            <AlertTriangle size={24} color="#F4212E" />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
            Application Error
          </h2>
          <p style={{ fontSize: 13, color: "#71767B", marginBottom: 24 }}>
            A critical error occurred. Please try refreshing the page.
          </p>
          <button
            onClick={reset}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 24px",
              borderRadius: 999,
              backgroundColor: "#EFF3F4",
              color: "#0F1419",
              fontSize: 13,
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
            }}
          >
            <RotateCcw size={14} />
            Refresh
          </button>
        </div>
      </body>
    </html>
  );
}

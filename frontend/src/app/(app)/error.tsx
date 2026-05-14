"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Global Error Boundary — Catches unhandled errors in the (app) route group.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import Link from "next/link";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to external service in production
    console.error("[EduVerse Error Boundary]", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-dvh bg-black px-4">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div className="w-14 h-14 rounded-full bg-[rgba(244,33,46,0.1)] flex items-center justify-center mx-auto mb-5">
          <AlertTriangle size={24} className="text-[#F4212E]" />
        </div>

        {/* Heading */}
        <h2 className="text-[18px] font-semibold text-[#E7E9EA] mb-2">
          Something went wrong
        </h2>

        {/* Message */}
        <p className="text-[13px] text-[#71767B] mb-1 leading-relaxed">
          An unexpected error occurred. Our team has been notified.
        </p>

        {/* Error detail (dev only) */}
        {process.env.NODE_ENV === "development" && (
          <div className="mt-3 p-3 rounded-lg bg-[#16181C] border border-[#2F3336] text-left overflow-x-auto">
            <p className="text-[11px] font-mono text-[#F4212E] break-all">
              {error.message}
            </p>
            {error.digest && (
              <p className="text-[10px] font-mono text-[#536471] mt-1">
                Digest: {error.digest}
              </p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-center gap-3 mt-6">
          <button
            onClick={reset}
            className="
              inline-flex items-center gap-2
              px-5 py-2.5
              rounded-full
              text-[13px] font-semibold
              bg-[#EFF3F4] text-[#0F1419]
              hover:bg-[#D7DBDC]
              transition-colors duration-150
            "
          >
            <RotateCcw size={14} />
            Try Again
          </button>
          <Link
            href="/dashboard"
            className="
              inline-flex items-center gap-2
              px-5 py-2.5
              rounded-full
              text-[13px] font-medium
              text-[#E7E9EA]
              border border-[#2F3336]
              hover:bg-[rgba(239,243,244,0.1)]
              transition-colors duration-150
            "
          >
            <Home size={14} />
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

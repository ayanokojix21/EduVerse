"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route boundary caught error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-[rgba(244,33,46,0.1)] flex items-center justify-center text-[var(--color-danger)] mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 className="text-[18px] font-bold text-[var(--color-text-main)] mb-2">
        Something went wrong!
      </h2>
      <p className="text-[13px] text-[var(--color-text-dim)] mb-6 max-w-md">
        {error.message || "An unexpected error occurred while rendering this page."}
      </p>
      <Button variant="ghost" onClick={() => reset()}>
        Try again
      </Button>
    </div>
  );
}

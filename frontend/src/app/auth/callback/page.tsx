"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Auth Callback Page — /auth/callback
//
// After Google OAuth, the backend redirects here with a JSON body containing
// { status, user_id, app_jwt }. We:
//   1. Try to read app_jwt from URL search params (some backends redirect with ?token=)
//   2. Fall back to reading the page body as JSON
//   3. Store app_jwt in localStorage
//   4. Redirect to /dashboard
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useAuth } from "@/lib/auth-context";

function CallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { saveToken } = useAuth();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    async function handleCallback() {
      try {
        // Strategy 1: JWT in URL param (?token= or ?app_jwt=)
        const tokenFromParam =
          searchParams.get("token") ?? searchParams.get("app_jwt");

        if (tokenFromParam) {
          saveToken(tokenFromParam);
          setStatus("success");
          router.replace("/dashboard");
          return;
        }

        // Strategy 2: Backend returned JSON in this page's body
        // (some OAuth flows redirect to /auth/callback with JSON response)
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/callback/google`,
          { credentials: "include" }
        );

        if (!res.ok) throw new Error(`Auth callback failed: ${res.status}`);

        const data = await res.json();
        const jwt = data.app_jwt ?? data.token;

        if (!jwt) throw new Error("No JWT found in OAuth response");

        saveToken(jwt);
        setStatus("success");
        router.replace("/dashboard");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Authentication failed";
        setErrorMsg(msg);
        setStatus("error");
      }
    }

    handleCallback();
  }, [router, searchParams, saveToken]);

  return (
    <div className="flex items-center justify-center min-h-dvh bg-black">
      <div className="flex flex-col items-center gap-6 max-w-sm w-full px-6 text-center">

        {/* Spinner / Icon */}
        {status === "loading" && (
          <>
            <div className="w-10 h-10 border-2 border-[#2F3336] border-t-[#EFF3F4] rounded-full animate-spin" />
            <div className="flex flex-col gap-1">
              <p className="text-[15px] font-medium text-[#E7E9EA]">Signing you in…</p>
              <p className="text-[13px] text-[#71767B]">Verifying your Google account</p>
            </div>
          </>
        )}

        {status === "success" && (
          <>
            <div
              className={[
                "w-10 h-10 rounded-full",
                "bg-[rgba(0,186,124,0.15)]",
                "flex items-center justify-center",
                "text-[#00BA7C] text-[20px]",
              ].join(" ")}
            >
              ✓
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-[15px] font-medium text-[#E7E9EA]">Signed in!</p>
              <p className="text-[13px] text-[#71767B]">Redirecting to your dashboard…</p>
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <div
              className={[
                "w-10 h-10 rounded-full",
                "bg-[rgba(244,33,46,0.15)]",
                "flex items-center justify-center",
                "text-[#F4212E] text-[20px]",
              ].join(" ")}
            >
              ✕
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-[15px] font-medium text-[#E7E9EA]">Authentication failed</p>
              <p className="text-[13px] text-[#71767B]">{errorMsg}</p>
              <button
                onClick={() => router.replace("/")}
                className={[
                  "mt-2 px-4 py-2 rounded-full",
                  "border border-[#2F3336]",
                  "text-[13px] text-[#E7E9EA]",
                  "hover:bg-[rgba(239,243,244,0.08)]",
                  "transition-colors duration-150",
                ].join(" ")}
              >
                Back to home
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Page export (Suspense boundary required for useSearchParams) ─────────────

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-dvh bg-black">
          <div className="w-10 h-10 border-2 border-[#2F3336] border-t-[#EFF3F4] rounded-full animate-spin" />
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}

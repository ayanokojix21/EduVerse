"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Settings Page — /settings
//
// Sections:
// 1. Google Connection status
// 2. Disconnect Google account
// 3. Danger Zone: Wipe all data
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { authApi } from "@/lib/api";
import type { AuthStatus } from "@/lib/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isWiping, setIsWiping] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        setIsLoading(true);
        const status = await authApi.status();
        setAuthStatus(status);
      } catch (err) {
        console.error("Failed to fetch auth status:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchStatus();
  }, []);

  // ── Disconnect Google ───────────────────────────────────────────────────

  const handleDisconnect = async () => {
    if (!confirm("Disconnect your Google account? You'll lose access to Classroom courses.")) return;
    try {
      setIsDisconnecting(true);
      setMessage(null);
      await authApi.disconnect();
      setAuthStatus((prev) => prev ? { ...prev, google_connected: false } : prev);
      setMessage({ type: "success", text: "Google account disconnected" });
    } catch (err) {
      console.error("Disconnect failed:", err);
      setMessage({ type: "error", text: "Failed to disconnect" });
    } finally {
      setIsDisconnecting(false);
    }
  };

  // ── Wipe All Data ──────────────────────────────────────────────────────

  const handleWipe = async () => {
    if (!confirm("⚠️ This will permanently delete ALL your data including chat history, indexed files, and profile. This cannot be undone. Continue?")) return;
    try {
      setIsWiping(true);
      setMessage(null);
      await authApi.wipe();
      logout();
    } catch (err) {
      console.error("Wipe failed:", err);
      setMessage({ type: "error", text: "Failed to wipe data" });
      setIsWiping(false);
    }
  };

  // ── Loading ─────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-[640px] mx-auto px-6 py-10 space-y-6">
        <div className="w-32 h-6 bg-[rgba(239,243,244,0.06)] rounded animate-pulse" />
        <div className="h-[140px] bg-[rgba(239,243,244,0.04)] rounded-[var(--radius-xl)] animate-pulse" />
        <div className="h-[140px] bg-[rgba(239,243,244,0.04)] rounded-[var(--radius-xl)] animate-pulse" />
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="max-w-[640px] mx-auto px-6 py-10 space-y-8">
      <h1 className="text-[22px] font-bold text-[var(--color-text-main)] animate-[fade-up_0.3s_ease-out_both]">
        Settings
      </h1>

      {/* Flash message */}
      {message && (
        <div
          className={`
            px-4 py-2.5 rounded-[var(--radius-lg)]
            text-[13px] font-medium
            animate-[fade-in_0.2s_ease-out]
            ${
              message.type === "success"
                ? "bg-[var(--color-success-dim)] text-[var(--color-success)]"
                : "bg-[var(--color-danger-dim)] text-[var(--color-danger)]"
            }
          `}
        >
          {message.text}
        </div>
      )}

      {/* Account Section */}
      <section className="animate-[fade-up_0.4s_ease-out_both]">
        <h2 className="text-[14px] font-semibold text-[var(--color-text-muted)] mb-3">
          Account
        </h2>
        <div className="border border-[var(--color-border)] rounded-[var(--radius-xl)] divide-y divide-[var(--color-border)]">
          {/* Email */}
          <div className="px-5 py-4 flex items-center justify-between">
            <div>
              <p className="text-[13px] text-[var(--color-text-dim)]">Email</p>
              <p className="text-[14px] text-[var(--color-text-main)] mt-0.5">
                {user?.email ?? authStatus?.email ?? "—"}
              </p>
            </div>
            {user?.is_guest && (
              <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-[rgba(239,243,244,0.06)] text-[var(--color-text-dim)]">
                Guest
              </span>
            )}
          </div>

          {/* Role */}
          <div className="px-5 py-4 flex items-center justify-between">
            <div>
              <p className="text-[13px] text-[var(--color-text-dim)]">Role</p>
              <p className="text-[14px] text-[var(--color-text-main)] mt-0.5 capitalize">
                {user?.role ?? authStatus?.role ?? "student"}
              </p>
            </div>
          </div>

          {/* Google Connection */}
          <div className="px-5 py-4 flex items-center justify-between">
            <div>
              <p className="text-[13px] text-[var(--color-text-dim)]">Google Classroom</p>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor: authStatus?.google_connected ? "#4ade80" : "#536471",
                  }}
                />
                <p className="text-[14px] text-[var(--color-text-main)]">
                  {authStatus?.google_connected ? "Connected" : "Not connected"}
                </p>
              </div>
            </div>

            {authStatus?.google_connected ? (
              <button
                onClick={handleDisconnect}
                disabled={isDisconnecting}
                className="
                  px-3 py-1.5
                  rounded-full
                  text-[12px] font-medium
                  text-[var(--color-danger)]
                  border border-[var(--color-danger)]
                  hover:bg-[var(--color-danger-dim)]
                  disabled:opacity-40
                  transition-colors duration-150
                "
              >
                {isDisconnecting ? "Disconnecting…" : "Disconnect"}
              </button>
            ) : (
              <a
                href={authApi.loginGoogleUrl()}
                className="
                  px-3 py-1.5
                  rounded-full
                  text-[12px] font-medium
                  text-[#1d9bf0]
                  border border-[#1d9bf0]
                  hover:bg-[rgba(29,155,240,0.08)]
                  transition-colors duration-150
                "
              >
                Connect
              </a>
            )}
          </div>
        </div>
      </section>

      {/* Danger Zone */}
      <section className="animate-[fade-up_0.5s_ease-out_both]">
        <h2 className="text-[14px] font-semibold text-[var(--color-danger)] mb-3">
          Danger Zone
        </h2>
        <div className="border border-[var(--color-danger)] rounded-[var(--radius-xl)] p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[14px] font-medium text-[var(--color-text-main)]">
                Delete all data
              </p>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-1 leading-[1.5]">
                Permanently delete your entire account data including all chat sessions,
                indexed documents, profile data, and mastery progress. This action cannot be undone.
              </p>
            </div>
            <button
              onClick={handleWipe}
              disabled={isWiping}
              className="
                flex-shrink-0
                px-4 py-2
                rounded-full
                text-[12px] font-semibold
                text-white
                bg-[var(--color-danger)]
                hover:bg-[#dc2626]
                disabled:opacity-40
                transition-colors duration-150
              "
            >
              {isWiping ? "Deleting…" : "Delete Everything"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

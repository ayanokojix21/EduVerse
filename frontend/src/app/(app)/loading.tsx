// ─────────────────────────────────────────────────────────────────────────────
// Loading State — Shown while (app) route group pages are loading.
// ─────────────────────────────────────────────────────────────────────────────

export default function AppLoading() {
  return (
    <div className="flex items-center justify-center min-h-dvh bg-black">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-[#2F3336] border-t-[#EFF3F4] rounded-full animate-spin" />
        <span className="text-[13px] text-[#71767B]">Loading…</span>
      </div>
    </div>
  );
}

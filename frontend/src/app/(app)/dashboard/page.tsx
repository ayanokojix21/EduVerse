import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

// Placeholder — P2 will replace this with the full course grid.
export default function DashboardPage() {
  return (
    <div className="flex items-center justify-center h-full min-h-[60vh]">
      <p className="text-[#71767B] text-[14px]">Dashboard — coming soon (P2)</p>
    </div>
  );
}

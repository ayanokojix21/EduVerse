"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Sidebar — Twitter-style left navigation
// Renders nav links: Dashboard, Chat, Profile. Admin section is conditional.
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  User,
  Settings,
  FlaskConical,
  BookOpen,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/profile",   label: "Profile",   icon: User },
  { href: "/settings",  label: "Settings",  icon: Settings },
];

const ADMIN_ITEMS: NavItem[] = [
  { href: "/admin/rl", label: "RLAIF Admin", icon: FlaskConical, adminOnly: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <nav
      className={[
        "flex flex-col",
        "w-[72px] xl:w-[240px]",       // Collapsed on md, expanded on xl
        "h-dvh sticky top-0",
        "border-r border-[#2F3336]",
        "py-3 px-2 xl:px-4",
        "bg-black",
        "flex-shrink-0",
        "overflow-y-auto overflow-x-hidden",
      ].join(" ")}
      aria-label="Main navigation"
    >
      {/* Logo / Brand */}
      <Link
        href="/dashboard"
        className={[
          "flex items-center gap-3 px-2 py-2.5 mb-2",
          "rounded-full hover:bg-[rgba(239,243,244,0.1)]",
          "transition-colors duration-150",
          "group",
        ].join(" ")}
        aria-label="EduVerse home"
      >
        <div
          className={[
            "w-8 h-8 rounded-full flex-shrink-0",
            "bg-[#EFF3F4] flex items-center justify-center",
          ].join(" ")}
        >
          <BookOpen size={16} className="text-black" />
        </div>
        <span className="hidden xl:block text-[17px] font-bold text-[#E7E9EA] tracking-tight">
          EduVerse
        </span>
      </Link>

      {/* Main Nav */}
      <ul className="flex flex-col gap-0.5 flex-1" role="list">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}

        {/* Admin Section */}
        {isAdmin && (
          <>
            <li className="mt-3 mb-1 px-2 hidden xl:block">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-[#536471]">
                Admin
              </span>
            </li>
            <li className="mt-3 mb-1 px-2 xl:hidden">
              <div className="h-px bg-[#2F3336]" />
            </li>
            {ADMIN_ITEMS.map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </>
        )}
      </ul>

      {/* User + Logout */}
      {user && (
        <div className="mt-auto flex flex-col gap-1 pt-2 border-t border-[#2F3336]">
          {/* User info */}
          <div className="flex items-center gap-2 px-2 py-2 rounded-xl xl:rounded-2xl">
            <div
              className={[
                "w-8 h-8 rounded-full flex-shrink-0",
                "bg-[#2F3336] flex items-center justify-center",
                "text-[13px] font-semibold text-[#E7E9EA] uppercase",
              ].join(" ")}
            >
              {user.is_guest ? "G" : (user.name?.[0] ?? user.email?.[0] ?? "U")}
            </div>
            <div className="hidden xl:flex flex-col min-w-0">
              <span className="text-[13px] font-medium text-[#E7E9EA] truncate">
                {user.is_guest ? "Guest" : (user.name ?? user.email ?? "Student")}
              </span>
              <span className="text-[11px] text-[#71767B] truncate">
                {user.is_guest ? "Guest session" : user.email}
              </span>
            </div>
          </div>

          {/* Logout */}
          <button
            onClick={logout}
            className={[
              "flex items-center gap-3 px-2 py-2.5",
              "rounded-full w-full",
              "text-[#71767B] hover:text-[#F4212E]",
              "hover:bg-[rgba(244,33,46,0.08)]",
              "transition-colors duration-150",
              "group",
            ].join(" ")}
            aria-label="Log out"
          >
            <LogOut size={20} className="flex-shrink-0" />
            <span className="hidden xl:block text-[15px] font-medium">Log out</span>
          </button>
        </div>
      )}
    </nav>
  );
}

// ─── NavLink sub-component ────────────────────────────────────────────────────

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const Icon = item.icon;
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

  return (
    <li>
      <Link
        href={item.href}
        className={[
          "flex items-center gap-3 px-2 py-2.5",
          "rounded-full",
          "transition-colors duration-150",
          "group",
          isActive
            ? "text-[#E7E9EA] font-bold"
            : "text-[#71767B] hover:text-[#E7E9EA] hover:bg-[rgba(239,243,244,0.1)]",
        ].join(" ")}
        aria-current={isActive ? "page" : undefined}
      >
        <Icon
          size={22}
          className={[
            "flex-shrink-0 transition-transform duration-150",
            "group-hover:scale-110",
            isActive ? "stroke-[2.5]" : "stroke-[1.5]",
          ].join(" ")}
        />
        <span className="hidden xl:block text-[17px]">{item.label}</span>
        {isActive && (
          <span className="xl:hidden sr-only">{item.label} (current)</span>
        )}
      </Link>
    </li>
  );
}

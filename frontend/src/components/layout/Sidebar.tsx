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
      className="flex flex-col w-[72px] xl:w-[240px] h-dvh sticky top-0 py-3 px-2 xl:px-4 bg-[var(--color-sidebar)] flex-shrink-0 overflow-y-auto overflow-x-hidden"
      style={{ borderRight: '1px solid var(--color-border)' }}
      aria-label="Main navigation"
    >
      {/* Logo / Brand */}
      <Link
        href="/dashboard"
        className="flex items-center gap-3 px-2 py-2.5 mb-4 rounded-full group"
        style={{ transition: 'background-color 0.15s ease' }}
        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(239,243,244,0.1)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        aria-label="EduVerse home"
      >
        <div className="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #EFF3F4 0%, #D7DBDC 100%)',
            boxShadow: '0 2px 8px rgba(239,243,244,0.15)',
          }}
        >
          <BookOpen size={16} className="text-black" />
        </div>
        <span className="hidden xl:block text-[17px] font-bold text-[#E7E9EA] tracking-tight">
          EduVerse
        </span>
      </Link>

      {/* Main Nav */}
      <ul className="flex flex-col gap-1 flex-1" role="list">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}

        {/* Admin Section */}
        {isAdmin && (
          <>
            <li className="mt-4 mb-1.5 px-2 hidden xl:block">
              <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#536471]">
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
        <div className="mt-auto flex flex-col gap-1.5 pt-3" style={{ borderTop: '1px solid var(--color-border)' }}>
          {/* User info */}
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl xl:rounded-2xl">
            <div
              className="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center text-[13px] font-semibold uppercase"
              style={{
                background: 'linear-gradient(135deg, #2F3336 0%, #1a1c1f 100%)',
                color: '#E7E9EA',
              }}
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
            className="flex items-center gap-3 px-2 py-2.5 rounded-full w-full group"
            style={{ transition: 'all 0.15s ease', color: '#71767B' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(244,33,46,0.08)';
              e.currentTarget.style.color = '#F4212E';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#71767B';
            }}
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
        className="flex items-center gap-3 px-3 py-2.5 rounded-xl group"
        style={{
          transition: 'all 0.2s ease',
          color: isActive ? 'var(--color-text-main)' : 'var(--color-text-muted)',
          fontWeight: isActive ? 600 : 500,
          backgroundColor: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
        }}
        onMouseEnter={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
            e.currentTarget.style.color = 'var(--color-text-main)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = 'var(--color-text-muted)';
          }
        }}
        aria-current={isActive ? "page" : undefined}
      >
        <div className="relative flex-shrink-0">
          <Icon
            size={22}
            style={{
              strokeWidth: isActive ? 2.5 : 1.5,
              transition: 'transform 0.15s ease',
            }}
          />
          {/* Active dot indicator */}
          {isActive && (
            <span
              className="absolute -right-0.5 -top-0.5 w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: '#1D9BF0' }}
            />
          )}
        </div>
        <span className="hidden xl:block text-[17px]">{item.label}</span>
        {isActive && (
          <span className="xl:hidden sr-only">{item.label} (current)</span>
        )}
      </Link>
    </li>
  );
}

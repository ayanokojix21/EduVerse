// ─────────────────────────────────────────────────────────────────────────────
// EduVerse — Next.js Middleware
//
// Protects authenticated routes under /(app)/ by checking for the JWT cookie
// or localStorage-synced token. Since localStorage is not available in
// middleware (edge runtime), we check for a cookie. However, our auth is
// localStorage-based, so we use a lightweight redirect-on-client approach:
//
// Strategy:
//   - Middleware checks for the `eduverse_jwt` cookie
//   - If not found, we still allow the request (client-side AuthGuard handles
//     the actual redirect for SPA flows)
//   - This middleware primarily handles direct URL navigation (e.g. user
//     types /dashboard into the address bar without a token)
//
// Protected paths:
//   /dashboard, /chat/*, /profile, /settings, /admin/*
//
// Public paths:
//   /, /auth/callback
// ─────────────────────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_PATHS = ["/", "/auth/callback"];

// Check if a path is public
function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

// Check if the path is a Next.js internal route
function isInternalPath(pathname: string): boolean {
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  );
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip internal routes and public paths
  if (isInternalPath(pathname) || isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Check for JWT in cookie (synced from localStorage by AuthProvider)
  const token = request.cookies.get("eduverse_jwt")?.value;

  if (!token) {
    // No cookie token — redirect to landing page
    // But only for direct navigation; SPA navigation is handled client-side
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // Basic JWT expiry check (decode without verification for edge runtime)
  try {
    const [, payload] = token.split(".");
    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));

    // Check expiry
    if (decoded.exp && Date.now() / 1000 > decoded.exp) {
      // Token expired — redirect to login
      const response = NextResponse.redirect(new URL("/", request.url));
      response.cookies.delete("eduverse_jwt");
      return response;
    }

    // Check admin routes
    if (pathname.startsWith("/admin") && decoded.role !== "admin") {
      // Non-admin trying to access admin route — redirect to dashboard
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  } catch {
    // Invalid token — redirect to login
    const response = NextResponse.redirect(new URL("/", request.url));
    response.cookies.delete("eduverse_jwt");
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - public folder assets
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};

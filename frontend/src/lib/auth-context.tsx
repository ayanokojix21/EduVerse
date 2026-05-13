"use client";

// ─────────────────────────────────────────────────────────────────────────────
// EduVerse — Auth Context
// Provides: user state, JWT token, login (Google / Guest), logout.
// JWT is persisted in localStorage under "eduverse_jwt".
// ─────────────────────────────────────────────────────────────────────────────

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { authApi } from "./api";
import type { DecodedJWT } from "./types";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  user_id: string;
  email?: string;
  name?: string;
  role: "student" | "admin";
  is_guest: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  loginAsGuest: () => Promise<void>;
  loginWithGoogle: () => void;
  logout: () => void;
}

// ─── JWT Helpers ──────────────────────────────────────────────────────────────

const JWT_KEY = "eduverse_jwt";

function decodeJWT(token: string): DecodedJWT | null {
  try {
    const [, payload] = token.split(".");
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded) as DecodedJWT;
  } catch {
    return null;
  }
}

function isTokenExpired(decoded: DecodedJWT): boolean {
  // `exp` is in seconds since epoch
  return Date.now() / 1000 > decoded.exp;
}

function jwtToUser(decoded: DecodedJWT): AuthUser {
  return {
    user_id: decoded.sub,
    email: decoded.email,
    name: decoded.name,
    role: decoded.role ?? "student",
    is_guest: decoded.is_guest ?? false,
  };
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(JWT_KEY);
    if (stored) {
      const decoded = decodeJWT(stored);
      if (decoded && !isTokenExpired(decoded)) {
        setToken(stored);
        setUser(jwtToUser(decoded));
      } else {
        // Expired — clear it
        localStorage.removeItem(JWT_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const saveToken = useCallback((jwt: string) => {
    localStorage.setItem(JWT_KEY, jwt);
    setToken(jwt);
    const decoded = decodeJWT(jwt);
    if (decoded) setUser(jwtToUser(decoded));
  }, []);

  const loginAsGuest = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await authApi.loginGuest();
      saveToken(res.app_jwt);
    } finally {
      setIsLoading(false);
    }
  }, [saveToken]);

  const loginWithGoogle = useCallback(() => {
    // Redirect browser to Google OAuth — backend handles callback
    window.location.href = authApi.loginGoogleUrl();
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(JWT_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isLoading,
      isAuthenticated: !!user,
      loginAsGuest,
      loginWithGoogle,
      logout,
    }),
    [user, token, isLoading, loginAsGuest, loginWithGoogle, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}

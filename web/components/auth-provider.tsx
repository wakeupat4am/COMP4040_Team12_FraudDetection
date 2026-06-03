"use client";

import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useState } from "react";

import { loginRequest } from "@/lib/api";
import { clearSession, persistSession, readSession } from "@/lib/session";
import type { AuthSession } from "@/lib/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  session: AuthSession | null;
  status: AuthStatus;
  login: (username: string, password: string) => Promise<AuthSession>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    const stored = readSession(window.sessionStorage);
    if (stored) {
      setSession(stored);
      setStatus("authenticated");
      return;
    }
    setStatus("anonymous");
  }, []);

  async function login(username: string, password: string): Promise<AuthSession> {
    const response = await loginRequest(username, password);
    const nextSession: AuthSession = {
      accessToken: response.access_token,
      role: response.role,
      tokenType: response.token_type,
      username,
    };
    persistSession(window.sessionStorage, nextSession);
    setSession(nextSession);
    setStatus("authenticated");
    return nextSession;
  }

  function logout(): void {
    clearSession(window.sessionStorage);
    setSession(null);
    setStatus("anonymous");
  }

  return <AuthContext.Provider value={{ session, status, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

"use client";

import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth as useClerkAuth, useClerk, useUser } from "@clerk/nextjs";

import { getCurrentUser } from "@/lib/api";
import type { AuthSession } from "@/lib/types";

type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

interface AuthContextValue {
  session: AuthSession | null;
  status: AuthStatus;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { signOut } = useClerk();
  const { user } = useUser();
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      if (!isLoaded) {
        setStatus("loading");
        return;
      }

      if (!isSignedIn) {
        setSession(null);
        setError(null);
        setStatus("anonymous");
        return;
      }

      try {
        setStatus("loading");
        const token = await getToken();
        if (!token) {
          throw new Error("Clerk did not return a session token.");
        }
        const currentUser = await getCurrentUser(token);
        if (cancelled) {
          return;
        }
        setSession({
          userId: user?.id ?? "",
          username: currentUser.username,
          email: user?.primaryEmailAddress?.emailAddress ?? user?.emailAddresses[0]?.emailAddress ?? null,
          role: currentUser.role,
        });
        setError(null);
        setStatus("authenticated");
      } catch (caughtError) {
        if (cancelled) {
          return;
        }
        setSession(null);
        setError(caughtError instanceof Error ? caughtError.message : "Unable to load authenticated user.");
        setStatus("error");
      }
    }

    void loadSession();
    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn, user?.id]);

  const logout = useCallback((): void => {
    void signOut();
    setSession(null);
    setStatus("anonymous");
  }, [signOut]);

  return <AuthContext.Provider value={{ session, status, logout, error }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

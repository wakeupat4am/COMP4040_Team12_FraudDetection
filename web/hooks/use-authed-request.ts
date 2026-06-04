"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";

export function useAuthedRequest() {
  const router = useRouter();
  const { session, logout } = useAuth();

  const run = useCallback(
    async <T,>(operation: (token: string) => Promise<T>): Promise<T> => {
      if (!session) {
        throw new Error("Authentication required");
      }

      try {
        return await operation(session.accessToken);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          logout();
          router.replace("/login");
        }
        throw error;
      }
    },
    [logout, router, session],
  );

  return { session, run };
}

"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth as useClerkAuth } from "@clerk/nextjs";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";

export function useAuthedRequest() {
  const router = useRouter();
  const { getToken } = useClerkAuth();
  const { session, logout } = useAuth();

  const run = useCallback(
    async <T,>(operation: (token: string) => Promise<T>): Promise<T> => {
      if (!session) {
        throw new Error("Authentication required");
      }
      const token = await getToken();
      if (!token) {
        throw new Error("Clerk session token is unavailable");
      }

      try {
        return await operation(token);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          logout();
          router.replace("/login");
        }
        throw error;
      }
    },
    [getToken, logout, router, session],
  );

  return { session, run };
}

"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import type { RoleValue } from "@/lib/types";

interface GuardedPageProps {
  title: string;
  description: string;
  children: ReactNode;
  allowedRoles?: RoleValue[];
}

export function GuardedPage({
  title,
  description,
  children,
  allowedRoles = ["analyst", "manager_admin"],
}: GuardedPageProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, status } = useAuth();

  useEffect(() => {
    if (status === "anonymous") {
      const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
      return;
    }

    if (status === "authenticated" && session && !allowedRoles.includes(session.role)) {
      router.replace("/cases");
    }
  }, [allowedRoles, pathname, router, session, status]);

  if (status === "loading") {
    return (
      <div className="fullscreen-center">
        <section className="panel">
          <p className="eyebrow">Session</p>
          <h2>Restoring analyst session</h2>
          <p>Checking local credentials and preparing the console.</p>
        </section>
      </div>
    );
  }

  if (status === "anonymous" || !session || !allowedRoles.includes(session.role)) {
    return (
      <div className="fullscreen-center">
        <section className="panel">
          <p className="eyebrow">Redirecting</p>
          <h2>Access is being verified</h2>
          <p>Routing you to the correct part of the dashboard.</p>
        </section>
      </div>
    );
  }

  return (
    <AppShell title={title} description={description}>
      {children}
    </AppShell>
  );
}

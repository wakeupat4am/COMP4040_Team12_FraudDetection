"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";

interface GuardedPageProps {
  title: string;
  description: string;
  children: ReactNode;
}

export function GuardedPage({ title, description, children }: GuardedPageProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { error, session, status } = useAuth();

  useEffect(() => {
    if (status === "anonymous") {
      const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [pathname, router, status]);

  if (status === "loading") {
    return (
      <div className="fullscreen-center">
        <section className="panel">
          <p className="eyebrow">Session</p>
          <h2>Restoring session</h2>
          <p>Checking local credentials and preparing the dashboard.</p>
        </section>
      </div>
    );
  }

  if (status === "anonymous" || !session) {
    if (error) {
      return (
        <div className="fullscreen-center">
          <section className="panel">
            <p className="eyebrow">Access</p>
            <h2>Unable to verify your session</h2>
            <p>{error}</p>
          </section>
        </div>
      );
    }

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

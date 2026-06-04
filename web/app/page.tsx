"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

export default function HomePage() {
  const router = useRouter();
  const { session, status } = useAuth();

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.replace("/cases");
      return;
    }
    if (status === "anonymous") {
      router.replace("/login");
    }
  }, [router, session, status]);

  return (
    <div className="fullscreen-center">
      <section className="panel landing-card">
        <p className="eyebrow">Fraud Analyst Dashboard</p>
        <h2>Preparing your workspace</h2>
        <p>Checking your session and routing you into the analyst workflow.</p>
      </section>
    </div>
  );
}

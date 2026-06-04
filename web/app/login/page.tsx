"use client";

import { SignIn } from "@clerk/nextjs";
import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { error, session, status } = useAuth();

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.replace(searchParams.get("next") ?? "/cases");
    }
  }, [router, searchParams, session, status]);

  return (
    <div className="fullscreen-center">
      <section className="panel landing-card">
        <p className="eyebrow">Fraud Ops Console</p>
        <h2>Sign in to the analyst dashboard</h2>
        {error ? <div className="error-banner">{error}</div> : null}
        <SignIn routing="path" path="/login" signUpUrl="/login" forceRedirectUrl={searchParams.get("next") ?? "/cases"} />
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="fullscreen-center">
          <section className="panel landing-card">
            <p className="eyebrow">Fraud Ops Console</p>
            <h2>Loading sign-in flow</h2>
            <p>Preparing the browser auth workflow.</p>
          </section>
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}

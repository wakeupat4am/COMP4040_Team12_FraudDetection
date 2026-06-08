"use client";

import { SignIn } from "@clerk/nextjs";
import { useSignIn } from "@clerk/nextjs";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, status } = useAuth();
  const { signIn } = useSignIn();
  const token = searchParams.get("token");
  const [tokenError, setTokenError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.replace(searchParams.get("next") ?? "/cases");
    }
  }, [router, searchParams, session, status]);

  useEffect(() => {
    if (!token || !signIn) {
      return;
    }

    let cancelled = false;

    async function completeTicketSignIn() {
      if (!token) {
        return;
      }

      const { error } = await signIn.ticket({ ticket: token });
      if (cancelled) {
        return;
      }
      if (error) {
        setTokenError(error.message || "Unable to complete token sign-in.");
        return;
      }

      if (signIn.status === "complete") {
        const next = searchParams.get("next") ?? "/cases";
        await signIn.finalize({
          navigate: async ({ decorateUrl }) => {
            const url = decorateUrl(next);
            if (url.startsWith("http")) {
              window.location.href = url;
              return;
            }
            router.replace(url);
          },
        });
      }
    }

    void completeTicketSignIn();
    return () => {
      cancelled = true;
    };
  }, [router, searchParams, signIn, token]);

  return (
    <div className="login-screen">
      {tokenError ? <div className="error-banner">{tokenError}</div> : null}
      <SignIn
        routing="hash"
        signUpUrl="/sign-up"
        forceRedirectUrl={searchParams.get("next") ?? "/cases"}
        appearance={{
          variables: {
            colorBackground: "#000000",
            colorPrimary: "#ffffff",
            colorText: "#ffffff",
            colorTextSecondary: "#a1a1aa",
            colorInputBackground: "#000000",
            colorInputText: "#ffffff",
            colorInputBorder: "#2a2a2a",
            colorShimmer: "#111111",
            colorDanger: "#ff6b6b",
          },
        }}
      />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={<div className="login-screen" />}
    >
      <LoginPageContent />
    </Suspense>
  );
}

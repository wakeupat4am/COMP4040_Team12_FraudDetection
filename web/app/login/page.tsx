"use client";

import { SignIn } from "@clerk/nextjs";
import { useSignIn } from "@clerk/nextjs";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
    <div className="grid min-h-screen place-items-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign in to Fraud Ops</CardTitle>
          <CardDescription>Access the analyst queue, scoring intake, and monitoring workspace.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {tokenError ? (
            <Alert variant="destructive">
              <AlertTitle>Token sign-in failed</AlertTitle>
              <AlertDescription>{tokenError}</AlertDescription>
            </Alert>
          ) : null}
          <SignIn
            routing="hash"
            signUpUrl="/sign-up"
            forceRedirectUrl={searchParams.get("next") ?? "/cases"}
            appearance={{
              variables: {
                colorBackground: "transparent",
                colorPrimary: "var(--primary)",
                colorText: "var(--foreground)",
                colorTextSecondary: "var(--muted-foreground)",
                colorInputBackground: "var(--input)",
                colorInputText: "var(--foreground)",
                colorInputBorder: "var(--border)",
                colorDanger: "var(--destructive)",
                borderRadius: "0.75rem",
              },
              elements: {
                cardBox: "shadow-none",
                card: "bg-transparent shadow-none border-0 p-0",
                footer: "bg-transparent",
              },
            }}
          />
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-background" />}>
      <LoginPageContent />
    </Suspense>
  );
}

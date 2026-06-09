"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";

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
    <div className="grid min-h-screen place-items-center bg-background p-6">
      {status === "error" ? (
        <Alert variant="destructive" className="max-w-md">
          <AlertTitle>Unable to prepare workspace</AlertTitle>
          <AlertDescription>Sign in again or contact an administrator if the backend user profile is missing.</AlertDescription>
        </Alert>
      ) : (
        <Card className="w-full max-w-md">
          <CardContent className="py-8">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary">Fraud Ops Dashboard</p>
            <h2 className="mt-2 font-heading text-xl font-medium">Preparing your workspace</h2>
            <p className="mt-2 text-sm text-muted-foreground">Checking your session and routing you into the case queue.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

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
      <div className="grid min-h-screen place-items-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardContent className="py-8">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Session</p>
            <h2 className="mt-2 font-heading text-xl font-medium">Restoring session</h2>
            <p className="mt-2 text-sm text-muted-foreground">Checking local credentials and preparing the dashboard.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="grid min-h-screen place-items-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardContent className="grid gap-4 py-8">
            <Alert variant="destructive">
              <AlertTitle>Unable to verify your account</AlertTitle>
              <AlertDescription>{error ?? "Your sign-in succeeded, but the backend user profile could not be loaded."}</AlertDescription>
            </Alert>
            <Button type="button" onClick={() => router.replace("/login")}>
              Return to sign in
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "anonymous" || !session) {
    if (error) {
      return (
        <div className="grid min-h-screen place-items-center bg-background p-6">
          <Alert variant="destructive" className="max-w-md">
            <AlertTitle>Unable to verify your session</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      );
    }

    return (
      <div className="grid min-h-screen place-items-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardContent className="py-8">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Redirecting</p>
            <h2 className="mt-2 font-heading text-xl font-medium">Access is being verified</h2>
            <p className="mt-2 text-sm text-muted-foreground">Routing you to the correct part of the dashboard.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <AppShell title={title} description={description}>
      {children}
    </AppShell>
  );
}

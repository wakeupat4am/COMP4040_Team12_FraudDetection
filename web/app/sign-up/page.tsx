"use client";

import { SignUp } from "@clerk/nextjs";
import { Suspense } from "react";

export default function SignUpPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-background" />}>
      <div className="grid min-h-screen place-items-center bg-background p-6">
        <SignUp
          routing="hash"
          signInUrl="/login"
          appearance={{
            variables: {
              colorBackground: "var(--card)",
              colorPrimary: "var(--primary)",
              colorText: "var(--foreground)",
              colorTextSecondary: "var(--muted-foreground)",
              colorInputBackground: "var(--input)",
              colorInputText: "var(--foreground)",
              colorInputBorder: "var(--border)",
              colorDanger: "var(--destructive)",
              borderRadius: "0.75rem",
            },
          }}
        />
      </div>
    </Suspense>
  );
}

"use client";

import { SignUp } from "@clerk/nextjs";
import { Suspense } from "react";

export default function SignUpPage() {
  return (
    <Suspense fallback={<div className="login-screen" />}>
      <div className="login-screen">
        <SignUp
          routing="hash"
          signInUrl="/login"
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
    </Suspense>
  );
}

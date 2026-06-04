import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";

import { AuthProvider } from "@/components/auth-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Fraud Analyst Dashboard",
  description: "Browser workflow for scoring, reviewing, and monitoring fraud cases.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          <AuthProvider>{children}</AuthProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}

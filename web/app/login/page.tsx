"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, session, status } = useAuth();
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("changeme-analyst");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.replace(searchParams.get("next") ?? "/cases");
    }
  }, [router, searchParams, session, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(username, password);
      router.replace(searchParams.get("next") ?? "/cases");
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        setError("Invalid credentials. Check the seeded analyst or manager username and password.");
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Unable to sign in.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fullscreen-center">
      <section className="panel landing-card">
        <p className="eyebrow">Fraud Ops Console</p>
        <h2>Sign in to the analyst dashboard</h2>
        <p>
          Use the backend-seeded credentials to access the queue, score new transactions, and review historical cases.
        </p>
        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field-group full-width">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              className="text-input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="field-group full-width">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="text-input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error ? <div className="error-banner full-width">{error}</div> : null}
          <div className="button-row">
            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? "Signing In..." : "Sign In"}
            </button>
          </div>
        </form>
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

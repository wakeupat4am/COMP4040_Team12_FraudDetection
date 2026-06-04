"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

interface AppShellProps {
  title: string;
  description: string;
  children: ReactNode;
}

export function AppShell({ title, description, children }: AppShellProps) {
  const pathname = usePathname();
  const { session, logout } = useAuth();

  const links = [
    { href: "/score", label: "Score Intake" },
    { href: "/cases", label: "Case Queue" },
    ...(session?.role === "manager_admin" ? [{ href: "/metrics", label: "Metrics" }] : []),
  ];

  return (
    <div className="dashboard">
      <aside className="sidebar panel">
        <div className="brand-lockup">
          <p className="eyebrow">Fraud Ops Console</p>
          <h1>Analyst Command</h1>
          <p className="sidebar-copy">
            Work a live fraud queue, rescore risky transactions, and close the loop with confirmed outcomes.
          </p>
        </div>
        <nav className="nav-list">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link key={link.href} href={link.href} className={`nav-link ${active ? "nav-link-active" : ""}`}>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="user-badge">
            <span className="eyebrow">Signed In</span>
            <strong>{session?.username}</strong>
            <span>{session?.role === "manager_admin" ? "Manager Admin" : "Analyst"}</span>
          </div>
          <button type="button" className="ghost-button" onClick={logout}>
            Log Out
          </button>
        </div>
      </aside>
      <main className="main-panel">
        <header className="hero-card panel">
          <div>
            <p className="eyebrow">Milestone 5 Frontend</p>
            <h2>{title}</h2>
            <p>{description}</p>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

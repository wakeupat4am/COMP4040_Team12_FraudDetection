"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/cases", label: "Case Queue" },
  { href: "/metrics", label: "Metrics" },
];

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Main navigation">
      {links.map((link) => {
        const active = pathname.startsWith(link.href);
        return (
          <Link key={link.href} href={link.href} className={`nav-link${active ? " active" : ""}`}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

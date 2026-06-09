"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3Icon, ClipboardListIcon, LogOutIcon, MenuIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button, buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

interface AppShellProps {
  title: string;
  description: string;
  children: ReactNode;
}

export function AppShell({ title, description, children }: AppShellProps) {
  const pathname = usePathname();
  const { session, logout } = useAuth();
  const displayIdentity = session?.email ?? session?.username ?? "Analyst";

  const links = [
    { href: "/cases", label: "Case Queue", icon: ClipboardListIcon, description: "Review and resolve cases" },
    { href: "/score", label: "Score Intake", icon: SparklesIcon, description: "Create a scored case" },
    { href: "/metrics", label: "Metrics", icon: BarChart3Icon, description: "Monitor queue health" },
  ];

  const navContent = (
    <>
      <div className="space-y-1">
        <div className="flex size-9 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <ShieldCheckIcon className="size-5" />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Fraud Ops</p>
          <h1 className="font-heading text-lg font-medium">Analyst Console</h1>
        </div>
      </div>
      <nav className="grid gap-1">
        {links.map((link) => {
          const Icon = link.icon;
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="size-4 shrink-0" />
              <span className="grid gap-0.5">
                <span className="font-medium leading-none">{link.label}</span>
                <span
                  className={cn(
                    "text-xs leading-tight",
                    active ? "text-primary-foreground/75" : "text-muted-foreground",
                  )}
                >
                  {link.description}
                </span>
              </span>
            </Link>
          );
        })}
      </nav>
    </>
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r bg-card/60 p-4 backdrop-blur lg:flex lg:flex-col">
        <div className="flex flex-1 flex-col gap-8">{navContent}</div>
        <Separator />
        <div className="mt-4 grid gap-3">
          <div className="rounded-2xl border bg-background/60 p-3">
            <p className="text-xs text-muted-foreground">Signed in as</p>
            <p className="truncate text-sm font-medium">{displayIdentity}</p>
            <p className="text-xs capitalize text-muted-foreground">{session?.role?.replace("_", " ") ?? "User"}</p>
          </div>
          <Button type="button" variant="outline" className="justify-start" onClick={logout}>
            <LogOutIcon className="size-4" />
            Log out
          </Button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
          <div className="flex min-h-16 items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <Sheet>
                <SheetTrigger render={<Button variant="outline" size="icon" className="lg:hidden" />}>
                  <MenuIcon className="size-4" />
                  <span className="sr-only">Open navigation</span>
                </SheetTrigger>
                <SheetContent side="left" className="w-80">
                  <SheetHeader>
                    <SheetTitle>Fraud Ops</SheetTitle>
                    <SheetDescription>Navigate the analyst workflow.</SheetDescription>
                  </SheetHeader>
                  <div className="grid gap-8 px-6">{navContent}</div>
                  <div className="mt-auto grid gap-3 p-6">
                    <Separator />
                    <SheetClose render={<Button type="button" variant="outline" className="justify-start" />}>
                      <LogOutIcon className="size-4" />
                      Close menu
                    </SheetClose>
                  </div>
                </SheetContent>
              </Sheet>
              <div className="min-w-0">
                <h2 className="truncate font-heading text-lg font-medium sm:text-xl">{title}</h2>
                <p className="hidden max-w-3xl truncate text-sm text-muted-foreground md:block">{description}</p>
              </div>
            </div>
            <div className="hidden items-center gap-2 sm:flex">
              <span className="rounded-2xl border px-3 py-1.5 text-xs text-muted-foreground">
                {displayIdentity}
              </span>
              <Button type="button" variant="ghost" size="icon" onClick={logout}>
                <LogOutIcon className="size-4" />
                <span className="sr-only">Log out</span>
              </Button>
            </div>
          </div>
        </header>

        <main className="mx-auto grid w-full max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:py-6">
          <section className="rounded-3xl border bg-card/60 p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary">Review workflow</p>
            <div className="mt-2 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <h1 className="font-heading text-2xl font-medium tracking-tight sm:text-3xl">{title}</h1>
                <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
              </div>
              <Link href="/score" className={cn(buttonVariants({ variant: "outline" }), "w-fit")}>
                <SparklesIcon className="size-4" />
                New score
              </Link>
            </div>
          </section>
          {children}
        </main>
      </div>
    </div>
  );
}

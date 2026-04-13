"use client";

import Link from "next/link";
import { site } from "@/lib/site";
import { track } from "@/lib/analytics";

const nav = [
  { href: "/", label: "Home" },
  { href: "/how-it-works/", label: "How it works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/docs/", label: "Docs" },
];

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-[color:var(--color-border)]/60 bg-[color:var(--color-background)]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-heading text-base font-semibold tracking-tight">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-[color:var(--color-primary)]" aria-hidden />
          {site.name}
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-[color:var(--color-muted-foreground)] md:flex">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={item.href === "/docs/" ? () => track("docs_click", { location: "header" }) : undefined}
              className="transition-colors hover:text-[color:var(--color-foreground)]"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <a
            href={`${site.appUrl}/login`}
            className="hidden rounded-md px-3 py-1.5 text-sm text-[color:var(--color-muted-foreground)] transition-colors hover:text-[color:var(--color-foreground)] sm:inline-block"
          >
            Sign in
          </a>
          <a
            href={`${site.appUrl}/signup`}
            onClick={() => track("signup_click", { location: "header" })}
            className="inline-flex items-center rounded-md bg-[color:var(--color-primary)] px-3 py-1.5 text-sm font-medium text-[color:var(--color-primary-foreground)] transition-opacity hover:opacity-90"
          >
            Get started
          </a>
        </div>
      </div>
    </header>
  );
}

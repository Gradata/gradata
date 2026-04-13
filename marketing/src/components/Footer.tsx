import Link from "next/link";
import { site } from "@/lib/site";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-32 border-t border-[color:var(--color-border)]/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-2">
          <div className="flex items-center gap-2 font-heading text-base font-semibold">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-[color:var(--color-primary)]" aria-hidden />
            {site.name}
          </div>
          <p className="mt-3 max-w-xs text-sm text-[color:var(--color-muted-foreground)]">
            {site.tagline}
          </p>
        </div>
        <div>
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-[color:var(--color-muted-foreground)]">
            Product
          </div>
          <ul className="space-y-2 text-sm">
            <li><Link href="/how-it-works/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">How it works</Link></li>
            <li><Link href="/pricing/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">Pricing</Link></li>
            <li><Link href="/docs/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">Docs</Link></li>
          </ul>
        </div>
        <div>
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-[color:var(--color-muted-foreground)]">
            Company
          </div>
          <ul className="space-y-2 text-sm">
            <li><Link href="/legal/privacy/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">Privacy</Link></li>
            <li><Link href="/legal/terms/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">Terms</Link></li>
            <li><Link href="/legal/dpa/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">DPA</Link></li>
            <li><Link href="/legal/sla/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">SLA</Link></li>
            <li><Link href="/legal/subprocessors/" className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">Subprocessors</Link></li>
            <li><a href={site.social.github} className="hover:text-[color:var(--color-foreground)] text-[color:var(--color-muted-foreground)]">GitHub</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[color:var(--color-border)]/60">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-3 px-4 py-6 text-xs text-[color:var(--color-muted-foreground)] sm:flex-row sm:items-center sm:px-6">
          <div>© {year} {site.name}. All rights reserved.</div>
          <div className="flex items-center gap-4">
            <a href={site.social.x} aria-label="X" className="hover:text-[color:var(--color-foreground)]">X</a>
            <a href={site.social.linkedin} aria-label="LinkedIn" className="hover:text-[color:var(--color-foreground)]">LinkedIn</a>
            <a href={site.social.github} aria-label="GitHub" className="hover:text-[color:var(--color-foreground)]">GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

"use client";

import Link from "next/link";
import { site } from "@/lib/site";
import { track } from "@/lib/analytics";
import { GlassCard } from "./GlassCard";

export function HomeFooterCta() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <GlassCard className="flex flex-col items-start gap-5 p-10 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">
            Ready to stop repeating yourself?
          </h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Free to start. BYO key. No credit card.
          </p>
        </div>
        <div className="flex gap-3">
          <a
            href={`${site.appUrl}/signup`}
            onClick={() => track("signup_click", { location: "home_footer_cta" })}
            className="inline-flex items-center rounded-md bg-[color:var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-primary-foreground)] hover:opacity-90"
          >
            Start free
          </a>
          <Link
            href="/pricing/"
            className="inline-flex items-center rounded-md border border-[color:var(--color-border)] px-5 py-2.5 text-sm font-medium hover:bg-[color:var(--color-card)]"
          >
            See pricing
          </Link>
        </div>
      </GlassCard>
    </section>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { Hero } from "@/components/Hero";
import { KpiProofRow } from "@/components/KpiProofRow";
import { GlassCard } from "@/components/GlassCard";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: `${site.name} — ${site.tagline}`,
  description: site.description,
  openGraph: {
    title: `${site.name} — ${site.tagline}`,
    description: site.description,
    url: site.url,
    type: "website",
  },
  alternates: { canonical: site.url },
};

export default function HomePage() {
  return (
    <>
      <Hero />

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="mb-10 max-w-2xl">
          <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
            Proof, not promises.
          </h2>
          <p className="mt-3 text-[color:var(--color-muted-foreground)]">
            Every number below is from blind evaluations on our public stress-test cohort.
            No self-grading, no cherry-picks.
          </p>
        </div>
        <KpiProofRow />
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grid gap-6 md:grid-cols-3">
          <GlassCard className="p-6">
            <div className="font-heading text-lg font-semibold">Captures every correction</div>
            <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
              Draft vs. final diffs flow into a single event stream. Nothing gets lost.
            </p>
          </GlassCard>
          <GlassCard className="p-6">
            <div className="font-heading text-lg font-semibold">Graduates lessons to rules</div>
            <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
              Instincts become patterns become rules as evidence compounds — scoped per task.
            </p>
          </GlassCard>
          <GlassCard className="p-6">
            <div className="font-heading text-lg font-semibold">Works with any model</div>
            <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
              BYO key. Claude, GPT, Gemini, local. The SDK is a thin layer on top.
            </p>
          </GlassCard>
        </div>
      </section>

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
    </>
  );
}

import type { Metadata } from "next";
import { Hero } from "@/components/Hero";
import { KpiProofRow } from "@/components/KpiProofRow";
import { GlassCard } from "@/components/GlassCard";
import { HomeFooterCta } from "@/components/HomeFooterCta";
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

      <HomeFooterCta />
    </>
  );
}

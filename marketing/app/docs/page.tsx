import type { Metadata } from "next";
import { GlassCard } from "@/components/GlassCard";
import { CodeBlock } from "@/components/CodeBlock";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Docs",
  description: "Install Gradata and run your first correction in under a minute.",
  openGraph: {
    title: "Docs — Gradata",
    description: "Install Gradata and run your first correction in under a minute.",
    url: `${site.url}/docs/`,
    type: "article",
  },
  alternates: { canonical: `${site.url}/docs/` },
};

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Docs
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
          Get started in 60 seconds.
        </h1>
        <p className="mt-4 text-[color:var(--color-muted-foreground)]">
          The full technical docs live on GitHub. Here&apos;s the shortest path from zero to your
          first graduated rule.
        </p>
      </header>

      <div className="space-y-6">
        <CodeBlock
          language="bash"
          code={`pip install gradata`}
          caption="Requires Python 3.10+"
        />
        <CodeBlock
          language="python"
          code={`from gradata import Gradata

brain = Gradata(profile="my-agent")

# Feed it your first correction
brain.correct(
    draft="Sure thing! Here's the TPS report.",
    final="Here is the TPS report.",
    task="email_reply",
)

# Inspect what the brain learned
print(brain.rules(task="email_reply"))`}
        />

        <GlassCard className="p-6">
          <div className="font-heading text-lg font-semibold">Full documentation</div>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Complete API reference, architecture deep-dives, and integration guides for Claude, GPT,
            Gemini, and local models are on GitHub.
          </p>
          <a
            href={site.docsUrl}
            className="mt-4 inline-flex items-center rounded-md border border-[color:var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[color:var(--color-card)]"
          >
            Read the docs on GitHub →
          </a>
        </GlassCard>
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import { GlassCard } from "@/components/GlassCard";
import { CodeBlock } from "@/components/CodeBlock";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Corrections become instincts, patterns, then rules. Rules with tight scope inject back into matching prompts. Gradata's graduation pipeline, explained.",
  openGraph: {
    title: "How it works — Gradata",
    description:
      "Corrections become instincts, patterns, then rules. Rules with tight scope inject back into matching prompts.",
    url: `${site.url}/how-it-works/`,
    type: "article",
  },
  alternates: { canonical: `${site.url}/how-it-works/` },
};

const STAGES = [
  {
    tag: "01",
    name: "INSTINCT",
    threshold: "confidence ≥ 0.40",
    description:
      "The first time you correct something, it's logged as an event with severity and edit-distance metadata.",
  },
  {
    tag: "02",
    name: "PATTERN",
    threshold: "confidence ≥ 0.60",
    description:
      "Repeated corrections on the same shape promote the lesson. Severity-weighted survival boosts confidence.",
  },
  {
    tag: "03",
    name: "RULE",
    threshold: "confidence ≥ 0.90",
    description:
      "Durable lessons graduate to rules and get injected into matching tasks (max 10 per session, scope-matched).",
  },
  {
    tag: "04",
    name: "META-RULE",
    threshold: "3+ graduated rules, LLM-synthesized with scoped applies_when",
    description:
      "Clusters of graduated rules are synthesized into meta-rules with tight scope tags. Ablation v3: LLM-synthesized meta-rules add value on smaller models, neutral on larger. Deterministic-template meta-rules regressed across models and are not shipped.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6">
      <header className="mb-12 max-w-2xl">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          How it works
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
          Corrections in. Judgment out.
        </h1>
        <p className="mt-4 text-[color:var(--color-muted-foreground)]">
          Every edit you make teaches the brain. The graduation pipeline promotes durable lessons
          into rules, and clusters of rules into meta-rules you can export and share.
        </p>
      </header>

      <section className="mb-14">
        <CodeBlock
          language="python"
          code={`from gradata import Gradata

brain = Gradata(profile="writing")

draft = llm.generate(prompt)
final = human_edit(draft)

# Every edit is a lesson. Severity is measured
# via edit distance; rules graduate automatically.
brain.correct(draft=draft, final=final, task="reply")

# Next time, matching rules inject into the prompt.
next_draft = llm.generate(prompt, context=brain.context_for("reply"))`}
          caption="Python SDK. AGPL-3.0. Works with any model."
        />
      </section>

      <section className="space-y-4">
        {STAGES.map((s) => (
          <GlassCard key={s.tag} className="p-6">
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="font-mono text-xs text-[color:var(--color-muted-foreground)]">{s.tag}</span>
              <span className="font-heading text-xl font-semibold">{s.name}</span>
              <span className="rounded-full border border-[color:var(--color-border)] px-2 py-0.5 text-xs text-[color:var(--color-muted-foreground)]">
                {s.threshold}
              </span>
            </div>
            <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">{s.description}</p>
          </GlassCard>
        ))}
      </section>

      <section className="mt-14">
        <GlassCard className="p-6">
          <div className="font-heading text-lg font-semibold">Injection, not retraining</div>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Matching rules are injected as structured context at prompt-time: no fine-tuning, no
            model upload, works across Claude, GPT, Gemini, or local models. Scope-matched per task,
            primacy/recency positioning, max 10 per session. Because base weights are frozen,
            replay-via-injection sidesteps the catastrophic forgetting that fine-tuning trips on.
          </p>
        </GlassCard>
      </section>
    </div>
  );
}

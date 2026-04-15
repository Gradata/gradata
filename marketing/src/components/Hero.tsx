"use client";

import { site } from "@/lib/site";
import { track } from "@/lib/analytics";
import { CodeBlock } from "./CodeBlock";

const INSTALL_SNIPPET = `pip install gradata

brain = Gradata()
brain.correct(draft, final)   # every edit teaches your brain`;

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="bg-gradient-radial absolute inset-0 z-0" aria-hidden />
      <div className="relative z-10 mx-auto max-w-6xl px-4 pb-20 pt-20 sm:px-6 sm:pt-28">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[color:var(--color-border)] bg-[color:var(--color-card)]/50 px-3 py-1 text-xs text-[color:var(--color-muted-foreground)]">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--color-accent)]" aria-hidden />
            Open source SDK. AGPL-3.0.
          </div>
          <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-6xl">
            AI that learns{" "}
            <span className="text-[color:var(--color-primary)]">the corrections</span>{" "}
            you keep making.
          </h1>
          <p className="mt-6 text-base text-[color:var(--color-muted-foreground)] sm:text-lg">
            Stop re-teaching your AI the same things. Gradata captures every correction, graduates it into a rule, and makes sure it never happens again.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href={`${site.appUrl}/signup`}
              onClick={() => track("signup_click", { location: "hero" })}
              className="inline-flex w-full items-center justify-center rounded-md bg-[color:var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-primary-foreground)] transition-opacity hover:opacity-90 sm:w-auto"
            >
              Start free
            </a>
            <a
              href="/how-it-works/"
              className="inline-flex w-full items-center justify-center rounded-md border border-[color:var(--color-border)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-foreground)] transition-colors hover:bg-[color:var(--color-card)] sm:w-auto"
            >
              How it works
            </a>
          </div>
        </div>
        <div className="mx-auto mt-14 max-w-xl">
          <CodeBlock
            language="bash"
            code={INSTALL_SNIPPET}
            copyable
            copyValue="pip install gradata"
            copyAriaLabel="Copy install command"
          />
        </div>
      </div>
    </section>
  );
}

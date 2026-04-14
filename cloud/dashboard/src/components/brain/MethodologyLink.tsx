'use client'

import { useState } from 'react'

/**
 * Truth-protocol surface: publishes our measurement methodology with
 * cited baselines and named limitations. Differentiator vs tools that
 * ship marketing claims without rigor (Mem0, Letta).
 *
 * Citations from SIM_DESIGN_RESEARCH:
 * - Duolingo HLR 9.5% retention gain (Settles & Meeder 2016, 12M sessions)
 * - SuperMemo two-component memory model (Wozniak 1995)
 * - Copilot RCT 55% faster, CI [21%-89%] (Peng 2023, 95 devs)
 * - Constitutional AI RLAIF methodology (Anthropic 2022)
 * - Multi-Evaluator Framework with consensus-deviation (2025)
 */
export function MethodologyLink() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-6 text-[11px] font-mono uppercase tracking-wider text-[var(--color-body)] underline-offset-4 hover:text-[var(--color-accent-blue)] hover:underline"
      >
        Methodology &amp; limitations →
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="glass relative max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-[0.625rem] p-7"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-brand opacity-50" />

            <div className="mb-5 flex items-baseline justify-between">
              <h3 className="text-[18px] font-semibold">Methodology &amp; limitations</h3>
              <button
                onClick={() => setOpen(false)}
                className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-[0.5rem] text-[24px] leading-none text-[var(--color-body)] hover:bg-white/[0.04] hover:text-[var(--color-text)]"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <section className="mb-5 space-y-2 text-[13px] leading-relaxed">
              <h4 className="mb-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent-blue)]">
                How we measure
              </h4>
              <p className="text-[var(--color-body)]">
                Correction events are classified by edit-distance severity, mapped to a 6-dimension
                taxonomy (WAVE2), and used to update Bayesian confidence on each lesson. Graduation
                thresholds: INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90). 95% CIs on reported
                metrics are exponential-decay fits, not linear extrapolations.
              </p>
            </section>

            <section className="mb-5 space-y-2 text-[13px] leading-relaxed">
              <h4 className="mb-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent-blue)]">
                Cited baselines
              </h4>
              <ul className="list-disc space-y-1 pl-5 text-[var(--color-body)]">
                <li>Duolingo HLR (Settles &amp; Meeder, ACL 2016): 9.5% retention gain, 12M sessions</li>
                <li>SuperMemo two-component memory model (Wozniak, 1995)</li>
                <li>Copilot RCT (Peng, 2023): 55% faster, 95% CI [21%, 89%], 95 devs</li>
                <li>Constitutional AI / RLAIF methodology (Anthropic, 2022)</li>
                <li>Multi-Evaluator Framework (2025): 3+ judges with consensus-deviation</li>
              </ul>
            </section>

            <section className="space-y-2 text-[13px] leading-relaxed">
              <h4 className="mb-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-warning)]">
                Named limitations
              </h4>
              <ul className="list-disc space-y-1 pl-5 text-[var(--color-body)]">
                <li>Validation is largely synthetic (MiroFish personas + Gemma4); real-user N is growing</li>
                <li>
                  &ldquo;93% correction reduction after ~3 sessions&rdquo; cites the sporadic cohort;
                  consistent-user cohort goes to 100% but over-fits; we report the defensible number
                </li>
                <li>Category classifier is being migrated from 5 legacy buckets to the 6-dim taxonomy</li>
                <li>Misfire count assumes current schema; suppression-flag backend is in progress</li>
              </ul>
            </section>
          </div>
        </div>
      )}
    </>
  )
}

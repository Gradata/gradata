'use client'

// TODO(phase-4): assemble widgets — KpiStrip, CorrectionDecayCurve, GraduationProgressBar,
// ActiveRulesPanel, CategoriesChart, MetaRulesGrid, ABProofPanel, ActivityFeed, etc.
// Per sim-revised plan (APPENDIX A), 6-dim taxonomy + privacy-first framing.

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[22px]">Overview</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Your brain's learning progress
        </p>
      </div>
      <div className="rounded-[0.625rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] p-8 backdrop-blur-xl">
        <p className="text-sm text-[var(--color-body)]">
          Dashboard widgets coming in Phase 4. Migration skeleton live.
        </p>
      </div>
    </div>
  )
}

'use client'

import { MetaRulesGrid } from '@/components/brain/MetaRulesGrid'

export default function MetaRulesPage() {
  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Meta Rules</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Universal principles crystallized from 3+ source rules · 2-layer grouping with Goal Alignment governing
        </p>
      </header>
      <MetaRulesGrid />
    </>
  )
}

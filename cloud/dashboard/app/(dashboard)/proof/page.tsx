'use client'

import { ABProofPanel } from '@/components/brain/ABProofPanel'
import { MethodologyLink } from '@/components/brain/MethodologyLink'

export default function ProofPage() {
  return (
    <div className="py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Proof</h1>
        <p className="mt-1 text-[14px] text-[var(--color-body)]">
          How we know your brain is actually learning: ablation data, methodology, and
          independent replications.
        </p>
      </div>
      <ABProofPanel />
      <MethodologyLink />
    </div>
  )
}

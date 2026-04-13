// TODO(backend): replace when A/B proof panel has real backing data.
// Numbers from S103_STAT_REPLICATION + S101 MARKETING_RESEARCH — validated claims
// with reported confidence intervals.

export interface ABDimension {
  dimension: string
  withPrinciples: number  // % success with rules active
  baseline: number        // % success without
  ciLow: number
  ciHigh: number
}

export const mockProof: ABDimension[] = [
  { dimension: 'Factual Integrity',   withPrinciples: 0.94, baseline: 0.68, ciLow: 0.90, ciHigh: 0.97 },
  { dimension: 'Clarity & Structure', withPrinciples: 0.89, baseline: 0.63, ciLow: 0.85, ciHigh: 0.93 },
  { dimension: 'Tone & Register',     withPrinciples: 0.82, baseline: 0.55, ciLow: 0.77, ciHigh: 0.87 },
  { dimension: 'Domain Fit',          withPrinciples: 0.86, baseline: 0.60, ciLow: 0.81, ciHigh: 0.90 },
  { dimension: 'Actionability',       withPrinciples: 0.78, baseline: 0.52, ciLow: 0.72, ciHigh: 0.84 },
]

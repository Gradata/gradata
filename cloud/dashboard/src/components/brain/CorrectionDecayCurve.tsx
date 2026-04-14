'use client'

import { Area, AreaChart, CartesianGrid, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { GlassCard } from '@/components/layout/GlassCard'
import { buildDecayCurve } from '@/lib/analytics-client'
import type { Correction } from '@/types/api'

/**
 * Hero viz: correction frequency decay per session, with Wozniak-style
 * exponential fit + 95% CI band. Per S103_STAT_REPLICATION cohort:
 * "93% correction reduction after ~3 sessions" is the defensible claim.
 * Methodology cited in tooltip: Duolingo HLR (Settles & Meeder 2016) +
 * SuperMemo two-component memory model (Wozniak 1995).
 */
export function CorrectionDecayCurve({
  corrections,
  range,
}: {
  corrections: Correction[]
  range: '7d' | '30d' | '90d'
}) {
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90
  const data = buildDecayCurve(corrections, days)
  const total = data.reduce((s, d) => s + d.empirical, 0)

  const first = data[0]?.empirical ?? 0
  const last = data[data.length - 1]?.empirical ?? 0
  const dropPct = first === 0 ? 0 : Math.max(0, ((first - last) / first) * 100)

  return (
    <GlassCard gradTop scanLine className="mb-4">
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h3 className="text-[15px] font-semibold">Correction Decay</h3>
          <p className="mt-1 text-[12px] text-[var(--color-body)]">
            Wozniak-style fit · {total} corrections · {range}
          </p>
        </div>
        <div className="text-right">
          <div className="font-[var(--font-heading)] text-[24px] font-bold text-gradient-brand">
            {dropPct.toFixed(0)}%
          </div>
          <div className="text-[10px] text-[var(--color-body)]">frequency drop</div>
        </div>
      </div>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fill: '#8895A7', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              tick={{ fill: '#8895A7', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={24}
            />
            <Tooltip
              contentStyle={{
                background: '#151D30',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: '#F8FAFC' }}
            />
            {/* 95% CI band from exponential decay fit */}
            <Area
              type="monotone"
              dataKey="ciHigh"
              stackId="ci"
              stroke="none"
              fill="#3A82FF"
              fillOpacity={0.08}
              name="95% CI upper"
            />
            <Area
              type="monotone"
              dataKey="ciLow"
              stackId="ci"
              stroke="none"
              fill="#0C1120"
              fillOpacity={1}
              name="95% CI lower"
            />
            {/* Empirical points as line */}
            <Line
              type="monotone"
              dataKey="empirical"
              stroke="#3A82FF"
              strokeWidth={2}
              dot={{ fill: '#3A82FF', r: 2 }}
              name="Corrections per day"
            />
            {/* Fitted decay curve */}
            <Line
              type="monotone"
              dataKey="fitted"
              stroke="#7C3AED"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="Exp. decay fit"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  )
}

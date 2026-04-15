import { GlassCard } from "./GlassCard";

type Kpi = {
  value: string;
  label: string;
  sub?: string;
};

const DEFAULT_KPIS: Kpi[] = [
  {
    value: "+2.7–5.7%",
    label: "Preference-adherence lift from graduated rules",
    sub: "Blind Haiku 4.5 judge, 432 trials across Sonnet, DeepSeek, qwen14b, gemma4",
  },
  {
    value: "3–10%",
    label: "Regression when rule content is randomized",
    sub: "Min 2022 random-label control: content carries the signal, not format",
  },
  {
    value: "4 / 4",
    label: "Models where graduated rules beat base prompt on preference",
    sub: "Same 16 tasks, 3 iterations each, rule set held at confidence ≥ 0.90",
  },
];

export function KpiProofRow({ kpis = DEFAULT_KPIS }: { kpis?: Kpi[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {kpis.map((kpi) => (
        <GlassCard key={kpi.label} className="p-6">
          <div className="font-heading text-4xl font-semibold tracking-tight text-[color:var(--color-foreground)]">
            {kpi.value}
          </div>
          <div className="mt-2 text-sm font-medium text-[color:var(--color-foreground)]">{kpi.label}</div>
          {kpi.sub && (
            <div className="mt-1 text-xs text-[color:var(--color-muted-foreground)]">{kpi.sub}</div>
          )}
        </GlassCard>
      ))}
    </div>
  );
}

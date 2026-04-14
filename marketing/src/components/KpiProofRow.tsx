import { GlassCard } from "./GlassCard";

type Kpi = {
  value: string;
  label: string;
  sub?: string;
};

const DEFAULT_KPIS: Kpi[] = [
  {
    value: "70%",
    label: "Win rate vs hand-written rules",
    sub: "Blind test across 3,000 comparisons",
  },
  {
    value: "93%",
    label: "Fewer corrections after ~3 sessions",
    sub: "Measured on S101 validation cohort",
  },
  {
    value: "65%",
    label: "Fewer tokens per task",
    sub: "Scoped rule injection vs full context",
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

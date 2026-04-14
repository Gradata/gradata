import { GlassCard } from "./GlassCard";
import { cn } from "@/lib/cn";

type Plan = {
  name: string;
  price: string;
  priceSub?: string;
  description: string;
  features: string[];
  cta: string;
  ctaHref: string;
  featured?: boolean;
};

export function PricingCard({ plan }: { plan: Plan }) {
  return (
    <GlassCard
      className={cn(
        "flex flex-col p-6",
        plan.featured && "ring-1 ring-[color:var(--color-primary)]/60"
      )}
    >
      {plan.featured && (
        <div className="mb-3 inline-flex w-max items-center rounded-full bg-[color:var(--color-primary)]/15 px-2 py-0.5 text-xs font-medium text-[color:var(--color-primary)]">
          Most popular
        </div>
      )}
      <div className="font-heading text-lg font-semibold">{plan.name}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <div className="font-heading text-3xl font-semibold tracking-tight">{plan.price}</div>
        {plan.priceSub && (
          <div className="text-sm text-[color:var(--color-muted-foreground)]">{plan.priceSub}</div>
        )}
      </div>
      <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">{plan.description}</p>
      <ul className="mt-5 flex-1 space-y-2 text-sm">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2">
            <span
              className="mt-1 inline-block h-1.5 w-1.5 flex-none rounded-full bg-[color:var(--color-accent)]"
              aria-hidden
            />
            <span className="text-[color:var(--color-foreground)]/90">{f}</span>
          </li>
        ))}
      </ul>
      <a
        href={plan.ctaHref}
        className={cn(
          "mt-6 inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-opacity",
          plan.featured
            ? "bg-[color:var(--color-primary)] text-[color:var(--color-primary-foreground)] hover:opacity-90"
            : "border border-[color:var(--color-border)] text-[color:var(--color-foreground)] hover:bg-[color:var(--color-card)]"
        )}
      >
        {plan.cta}
      </a>
    </GlassCard>
  );
}

export type { Plan };

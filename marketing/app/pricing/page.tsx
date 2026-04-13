import type { Metadata } from "next";
import { PricingCard, type Plan } from "@/components/PricingCard";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Start free. Upgrade when you're ready for cloud sync, teams, or enterprise controls. BYO key.",
  openGraph: {
    title: "Pricing — Gradata",
    description:
      "Start free. Upgrade when you're ready for cloud sync, teams, or enterprise controls. BYO key.",
    url: `${site.url}/pricing/`,
    type: "website",
  },
  alternates: { canonical: `${site.url}/pricing/` },
};

const PLANS: Plan[] = [
  {
    name: "Free",
    price: "$0",
    priceSub: "/forever",
    description: "The open source SDK. Local-only brain. BYO key.",
    features: [
      "pip install gradata",
      "Local brain (SQLite + JSONL)",
      "Correction capture + graduation",
      "Works with any model",
      "AGPL-3.0",
    ],
    cta: "Install the SDK",
    ctaHref: site.docsUrl,
  },
  {
    name: "Cloud",
    price: "$29",
    priceSub: "/month",
    description: "Hosted brain, sync across machines, metrics dashboard.",
    features: [
      "Everything in Free",
      "Hosted brain + sync",
      "Metrics dashboard",
      "Rule marketplace access",
      "Email support",
    ],
    cta: "Start free trial",
    ctaHref: `${site.appUrl}/signup?plan=cloud`,
    featured: true,
  },
  {
    name: "Team",
    price: "$99",
    priceSub: "/seat/month",
    description: "Shared brains, role-based access, audit logs for up to 10 seats.",
    features: [
      "Everything in Cloud",
      "Shared team brains",
      "Role-based access control",
      "Audit logs",
      "Priority support",
    ],
    cta: "Start team trial",
    ctaHref: `${site.appUrl}/signup?plan=team`,
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "SSO/SAML, on-prem option, SLAs, and dedicated success.",
    features: [
      "Everything in Team",
      "SSO / SAML",
      "On-prem / VPC deployment",
      "SLA + dedicated CSM",
      "Security review + DPA",
    ],
    cta: "Contact sales",
    ctaHref: "mailto:hello@gradata.ai?subject=Gradata%20Enterprise",
  },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <header className="mx-auto mb-14 max-w-2xl text-center">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Pricing
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
          Simple, honest pricing.
        </h1>
        <p className="mt-4 text-[color:var(--color-muted-foreground)]">
          BYO model key. The SDK is free and open source forever. Pay only for hosted sync,
          team collaboration, and enterprise controls.
        </p>
      </header>
      <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
        {PLANS.map((plan) => (
          <PricingCard key={plan.name} plan={plan} />
        ))}
      </div>
      <p className="mt-10 text-center text-xs text-[color:var(--color-muted-foreground)]">
        Prices in USD. Taxes may apply. Cancel anytime.
      </p>
    </div>
  );
}

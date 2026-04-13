import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Subprocessors",
  description:
    "Third-party subprocessors Gradata engages to deliver the hosted service.",
  alternates: { canonical: `${site.url}/legal/subprocessors/` },
  robots: { index: true, follow: true },
};

type Subprocessor = {
  name: string;
  purpose: string;
  dataCategories: string;
  location: string;
  website: string;
};

const subprocessors: Subprocessor[] = [
  {
    name: "Railway",
    purpose: "Application hosting and deployment (api.gradata.ai)",
    dataCategories: "All data in transit through the API",
    location: "United States (us-west)",
    website: "https://railway.app",
  },
  {
    name: "Supabase",
    purpose: "Managed Postgres database and authentication",
    dataCategories: "Account identifiers, workspace + brain metadata, corrections, lessons, events",
    location: "United States (AWS us-east-1)",
    website: "https://supabase.com",
  },
  {
    name: "Stripe",
    purpose: "Payment processing and subscription billing",
    dataCategories: "Billing email, Stripe customer ID, subscription status (no card data stored by Gradata)",
    location: "United States / EU",
    website: "https://stripe.com",
  },
  {
    name: "Cloudflare",
    purpose: "DNS, CDN, and DDoS protection for marketing + dashboard",
    dataCategories: "IP address, request metadata (transit only)",
    location: "Global edge network",
    website: "https://cloudflare.com",
  },
  {
    name: "Sentry",
    purpose: "Error monitoring and performance tracking (optional — enabled when GRADATA_SENTRY_DSN is set)",
    dataCategories: "Stack traces, request metadata, user_id (no payload content)",
    location: "United States / EU (configurable)",
    website: "https://sentry.io",
  },
];

export default function SubprocessorsPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">Subprocessors</h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: April 2026 &middot; DRAFT — pending legal review
        </p>
      </header>

      <div className="space-y-6">
        <section className="rounded border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-200/90">
          This page lists the third parties Gradata engages to deliver the
          hosted Gradata Cloud service. The open source SDK running locally
          uses none of these. See our{" "}
          <a href="/legal/dpa/" className="underline">DPA</a> for the terms
          under which subprocessors handle Personal Data.
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">Current subprocessors</h2>
          <div className="mt-4 space-y-4">
            {subprocessors.map((sp) => (
              <div
                key={sp.name}
                className="rounded border border-[color:var(--color-border)]/60 bg-[color:var(--color-border)]/10 p-4"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <a
                    href={sp.website}
                    className="font-heading text-lg font-semibold underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {sp.name}
                  </a>
                  <span className="text-xs uppercase tracking-wider text-[color:var(--color-muted-foreground)]">
                    {sp.location}
                  </span>
                </div>
                <dl className="mt-3 space-y-2 text-sm text-[color:var(--color-muted-foreground)]">
                  <div>
                    <dt className="inline font-medium text-[color:var(--color-foreground)]/80">Purpose:&nbsp;</dt>
                    <dd className="inline">{sp.purpose}</dd>
                  </div>
                  <div>
                    <dt className="inline font-medium text-[color:var(--color-foreground)]/80">Data categories:&nbsp;</dt>
                    <dd className="inline">{sp.dataCategories}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">Change notifications</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            We provide 30 days&apos; advance notice before adding or replacing a
            subprocessor. Workspace admins receive notifications by email and
            the change is reflected on this page. To subscribe to updates or
            raise an objection, contact{" "}
            <a href="mailto:privacy@gradata.ai" className="underline">privacy@gradata.ai</a>.
          </p>
        </section>
      </div>
    </article>
  );
}

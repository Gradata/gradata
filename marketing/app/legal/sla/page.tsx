import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Service Level Agreement (SLA)",
  description:
    "Gradata's uptime target, support response times, and incident communication commitments.",
  alternates: { canonical: `${site.url}/legal/sla/` },
  robots: { index: true, follow: true },
};

export default function SlaPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">
          Service Level Agreement
        </h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: April 2026 &middot; DRAFT — pending legal review
        </p>
      </header>

      <div className="space-y-6">
        <section className="rounded border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-200/90">
          This SLA is a draft provided as a reasonable starting point for
          procurement discussions. It has not been reviewed by outside counsel.
          Executed enterprise SLAs may supersede this document via order form.
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">1. Uptime target</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Gradata targets <strong>99.9% monthly uptime</strong> for the hosted
            cloud API and dashboard (excluding scheduled maintenance announced at
            least 48 hours in advance and events outside Gradata&apos;s reasonable
            control). Monthly uptime is calculated as:
          </p>
          <pre className="mt-3 rounded bg-[color:var(--color-border)]/30 p-3 text-xs text-[color:var(--color-muted-foreground)]">
{`uptime % = (total_minutes - downtime_minutes) / total_minutes × 100`}
          </pre>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            &quot;Downtime&quot; means a sustained period (&gt;2 consecutive minutes) where
            the API returns 5xx errors for at least 50% of requests from Gradata&apos;s
            external synthetic monitors.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">2. Service credits</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-[color:var(--color-muted-foreground)]">
                <th className="py-2">Monthly uptime</th>
                <th className="py-2">Service credit</th>
              </tr>
            </thead>
            <tbody className="text-[color:var(--color-muted-foreground)]">
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">99.9% – 100%</td><td className="py-2">0%</td></tr>
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">99.0% – 99.89%</td><td className="py-2">10% of monthly fee</td></tr>
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">95.0% – 98.99%</td><td className="py-2">25% of monthly fee</td></tr>
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">below 95.0%</td><td className="py-2">50% of monthly fee</td></tr>
            </tbody>
          </table>
          <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
            Credits are claimed by emailing{" "}
            <a href="mailto:support@gradata.ai" className="underline">support@gradata.ai</a>{" "}
            within 30 days of the affected month. Credits are applied to the
            following invoice and are the sole remedy for missed uptime targets.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">3. Support response times</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-[color:var(--color-muted-foreground)]">
                <th className="py-2">Severity</th>
                <th className="py-2">First response</th>
                <th className="py-2">Coverage</th>
              </tr>
            </thead>
            <tbody className="text-[color:var(--color-muted-foreground)]">
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">P1 &mdash; production down</td><td className="py-2">1 hour</td><td className="py-2">24&times;7 (Team+)</td></tr>
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">P2 &mdash; major degradation</td><td className="py-2">4 business hours</td><td className="py-2">business days</td></tr>
              <tr className="border-t border-[color:var(--color-border)]/60"><td className="py-2">P3 &mdash; question / bug</td><td className="py-2">1 business day</td><td className="py-2">business days</td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">4. Incident communication</h2>
          <ul className="mt-2 space-y-1 text-sm text-[color:var(--color-muted-foreground)]">
            <li>Active incidents are posted to <code>status.gradata.ai</code> within 15 minutes of detection.</li>
            <li>Customer-impacting incidents trigger an email to workspace admins.</li>
            <li>Post-mortems for P1 incidents are published within 5 business days, including root cause and remediation steps.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">5. Exclusions</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            This SLA does not apply to: the open source SDK running locally,
            beta/preview features, downtime caused by Customer misuse, third-party
            outages outside Gradata&apos;s control (see{" "}
            <a href="/legal/subprocessors/" className="underline">subprocessors</a>),
            or scheduled maintenance announced 48+ hours in advance.
          </p>
        </section>

        <section>
          <p className="text-xs text-[color:var(--color-muted-foreground)]">
            Contact:{" "}
            <a href="mailto:support@gradata.ai" className="underline">support@gradata.ai</a>
          </p>
        </section>
      </div>
    </article>
  );
}

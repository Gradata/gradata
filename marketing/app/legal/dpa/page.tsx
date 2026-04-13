import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Data Processing Agreement (DPA)",
  description:
    "Gradata's Data Processing Agreement — GDPR Article 28 clauses covering how we process customer data on your behalf.",
  alternates: { canonical: `${site.url}/legal/dpa/` },
  // Draft — pending legal review. Do not index until sign-off.
  robots: { index: false, follow: false },
};

export default function DpaPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">
          Data Processing Agreement
        </h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: April 2026 &middot; DRAFT — pending legal review
        </p>
      </header>

      <div className="space-y-6">
        <section className="rounded border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-200/90">
          This DPA is a draft provided as a reasonable starting point for
          enterprise procurement. It has not been reviewed by outside counsel.
          For executed agreements, contact{" "}
          <a href="mailto:legal@gradata.ai" className="underline">legal@gradata.ai</a>.
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">1. Definitions</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            &quot;Controller&quot;, &quot;Processor&quot;, &quot;Personal Data&quot;, &quot;Data Subject&quot;,
            &quot;Processing&quot;, and &quot;Sub-processor&quot; carry the meanings given in the
            EU General Data Protection Regulation 2016/679 (&quot;GDPR&quot;). &quot;Customer&quot; is the
            entity that has agreed to Gradata&apos;s Terms of Service. &quot;Gradata&quot; is the
            Processor. &quot;Services&quot; means the hosted Gradata cloud platform.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">2. Scope & roles</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Customer is the Controller of Personal Data submitted to the Services.
            Gradata Processes Personal Data only on documented instructions from
            Customer (as set forth in the Terms of Service, the product&apos;s in-app
            configuration, and this DPA) unless required to do so by applicable law.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">3. Subject matter & duration</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            The subject matter is the provision of the Services. Duration matches
            the Customer&apos;s active subscription plus up to 30 days for post-
            termination deletion as described in Section 9.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">4. Nature & purpose of processing</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Hosting, storing, transmitting, analyzing, and serving Customer data
            (corrections, lessons, events, rules, account metadata) as required to
            deliver the Services. Gradata does not train foundation models on
            Customer data and does not sell Personal Data.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">5. Categories of data</h2>
          <ul className="mt-2 space-y-1 text-sm text-[color:var(--color-muted-foreground)]">
            <li>Account identifiers (email, user UUID, workspace membership)</li>
            <li>Billing metadata (Stripe customer + subscription IDs; no card data)</li>
            <li>Product content Customer chooses to sync (corrections, lessons,
                meta-rules, event logs)</li>
            <li>Telemetry (request logs, error reports via Sentry if enabled)</li>
          </ul>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">6. Confidentiality</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Personnel authorized to Process Personal Data are bound by written
            confidentiality obligations or statutory duties of confidentiality.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">7. Security measures (Art. 32)</h2>
          <ul className="mt-2 space-y-1 text-sm text-[color:var(--color-muted-foreground)]">
            <li>Encryption in transit (TLS 1.2+) and at rest (Postgres + managed storage)</li>
            <li>Row-level security on all multi-tenant tables</li>
            <li>Principle of least privilege for production access; audit logs for
                admin actions</li>
            <li>Regular dependency scanning and secret rotation</li>
            <li>Incident response runbook (see{" "}
                <a href="https://github.com/Gradata/gradata/blob/main/cloud/RUNBOOK-INCIDENT.md" className="underline">cloud/RUNBOOK-INCIDENT.md</a>)</li>
          </ul>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">8. Sub-processors</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Customer provides general written authorisation for Gradata to engage
            Sub-processors. The current list is published at{" "}
            <a href="/legal/subprocessors/" className="underline">/legal/subprocessors</a>.
            Gradata will give Customer 30 days&apos; notice (via the same page and
            email where provided) before adding or replacing a Sub-processor;
            Customer may object in writing, in which case the parties will work in
            good faith to resolve the objection.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">9. Data subject rights</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Gradata provides self-service tools for access, export, and erasure
            (Articles 15 &amp; 17) via the account settings UI and the{" "}
            <code>/me/export</code> and <code>/me/delete</code> API endpoints. Upon
            erasure, Personal Data enters a soft-delete window with a target
            purge horizon of 30 days, executed via a scheduled purge workflow.
            Gradata will assist Customer in responding to Data Subject
            requests within 10 business days of a written request to{" "}
            <a href="mailto:privacy@gradata.ai" className="underline">privacy@gradata.ai</a>.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">10. Personal data breaches</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Gradata will notify Customer without undue delay (and in any event
            within 72 hours of confirmation) after becoming aware of a Personal
            Data breach, and will provide information reasonably required for
            Customer to meet its notification obligations under Article 33.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">11. International transfers</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Where Personal Data is transferred from the EEA/UK/Switzerland to a
            third country, the parties rely on the EU Standard Contractual Clauses
            (2021/914) and the UK International Data Transfer Addendum, which are
            deemed incorporated into this DPA by reference.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">12. Audit</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            On reasonable written notice (no more than once per 12 months, absent
            a documented incident), Gradata will make available information
            necessary to demonstrate compliance with Article 28, including
            third-party attestations where available.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">13. Return or deletion</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Upon termination, Customer may export all Personal Data via the
            self-service tools described in Section 9. Gradata targets deletion
            of remaining Personal Data within 30 days of termination via its
            scheduled purge workflow, except where retention is required by law.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-xl font-semibold">14. Liability & precedence</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Liability under this DPA is subject to the limitations in the
            underlying Terms of Service. Where this DPA conflicts with the Terms
            regarding Processing of Personal Data, this DPA controls.
          </p>
        </section>

        <section>
          <p className="text-xs text-[color:var(--color-muted-foreground)]">
            Contact:{" "}
            <a href="mailto:legal@gradata.ai" className="underline">legal@gradata.ai</a>{" "}
            for a countersigned copy or redlines.
          </p>
        </section>
      </div>
    </article>
  );
}

import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Gradata collects, uses, and protects your data.",
  alternates: { canonical: `${site.url}/legal/privacy/` },
  robots: { index: true, follow: true },
};

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">Privacy Policy</h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: April 2026
        </p>
      </header>

      <div className="prose-invert space-y-6 text-[color:var(--color-foreground)]/90">
        <section>
          <h2 className="font-heading text-xl font-semibold">Overview</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Gradata (&quot;we&quot;, &quot;us&quot;) provides an open source SDK and an optional
            hosted cloud service. The SDK runs locally and stores your brain on your machine. The
            cloud service stores data you explicitly sync.
          </p>
        </section>
        <section>
          <h2 className="font-heading text-xl font-semibold">Data we collect</h2>
          <ul className="mt-2 space-y-1 text-sm text-[color:var(--color-muted-foreground)]">
            <li>Account email and authentication metadata</li>
            <li>Brains you choose to sync to our cloud</li>
            <li>Billing information (processed by Stripe)</li>
            <li>Basic product analytics (page views, feature usage)</li>
          </ul>
        </section>
        <section>
          <h2 className="font-heading text-xl font-semibold">Your rights</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            You can export or delete your data at any time. For privacy requests, contact{" "}
            <a href="mailto:privacy@gradata.ai" className="underline">privacy@gradata.ai</a>.
          </p>
        </section>
        <section>
          <p className="text-xs text-[color:var(--color-muted-foreground)]">
            This is a stub. Full policy is being finalized. Questions in the interim go to{" "}
            <a href="mailto:privacy@gradata.ai" className="underline">privacy@gradata.ai</a>.
          </p>
        </section>
      </div>
    </article>
  );
}

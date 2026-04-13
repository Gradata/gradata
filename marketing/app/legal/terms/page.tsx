import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern your use of Gradata.",
  alternates: { canonical: `${site.url}/legal/terms/` },
  robots: { index: true, follow: true },
};

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">Terms of Service</h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: April 2026
        </p>
      </header>

      <div className="space-y-6">
        <section>
          <h2 className="font-heading text-xl font-semibold">Acceptance</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            By using Gradata, you agree to these terms. The open source SDK is licensed under
            AGPL-3.0 — see the LICENSE file in the repository.
          </p>
        </section>
        <section>
          <h2 className="font-heading text-xl font-semibold">Acceptable use</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            Don&apos;t use Gradata to violate laws, infringe rights, or attack others&apos; systems.
            Don&apos;t reverse-engineer the hosted service beyond what AGPL-3.0 permits for the SDK.
          </p>
        </section>
        <section>
          <h2 className="font-heading text-xl font-semibold">Service availability</h2>
          <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">
            The hosted cloud service is provided &quot;as-is&quot;. Enterprise plans include an
            explicit SLA; see your order form.
          </p>
        </section>
        <section>
          <p className="text-xs text-[color:var(--color-muted-foreground)]">
            This is a stub. Full terms are being finalized. Questions to{" "}
            <a href="mailto:legal@gradata.ai" className="underline">legal@gradata.ai</a>.
          </p>
        </section>
      </div>
    </article>
  );
}

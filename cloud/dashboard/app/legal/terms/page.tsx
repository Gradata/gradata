import Link from 'next/link'
import type { Metadata } from 'next'
import { GlassCard } from '@/components/layout/GlassCard'

export const metadata: Metadata = {
  title: 'Terms of Service — Gradata',
  description:
    'The agreement between you and Gradata: how you can use the service, what we promise, and what we don’t.',
}

const LAST_UPDATED = '2026-04-13'

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-10 md:py-16">
      <div className="mx-auto max-w-3xl">
        <header className="mb-8">
          <Link
            href="/"
            className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-body)] underline-offset-4 hover:text-[var(--color-accent-blue)] hover:underline"
          >
            ← Back to Gradata
          </Link>
          <h1 className="mt-4 text-[32px] leading-tight md:text-[40px]">Terms of Service</h1>
          <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-[var(--color-body)]">
            Last updated {LAST_UPDATED}
          </p>
        </header>

        <GlassCard gradTop className="mb-6">
          <p className="text-[14px] leading-relaxed text-[var(--color-body)]">
            These terms govern your use of Gradata (the SDK and the cloud service at app.gradata.ai and
            api.gradata.ai). By creating an account or using the service, you agree to them. If you
            are agreeing on behalf of a company, you confirm that you have authority to bind that
            company.
          </p>
        </GlassCard>

        <Section title="1. The service">
          <p>
            Gradata is an AI memory layer that learns from your corrections. It has two parts:
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>
              The <strong>SDK</strong>, distributed under the GNU Affero General Public License v3.0,
              which runs on your machine and maintains a local brain file.
            </li>
            <li>
              The <strong>cloud dashboard and API</strong>, proprietary hosted services that provide
              observability, team features, billing, and the graduation engine that produces
              synthesized principles.
            </li>
          </ul>
          <p className="mt-3">
            The service may change. We add features, retire features, and change how things work. We
            aim to give useful notice for breaking changes, but we do not promise any specific feature
            will exist forever.
          </p>
        </Section>

        <Section title="2. Your account">
          <p>
            You must provide accurate account information and keep your credentials safe. You are
            responsible for everything that happens under your account, including API key usage. If
            you suspect your credentials or API key have been compromised, rotate them immediately and
            email <EmailLink>support@gradata.ai</EmailLink>.
          </p>
          <p className="mt-3">
            You must be at least 16 years old to use Gradata. If you are using Gradata in a country
            that sets a higher age of digital consent, you must meet that threshold.
          </p>
        </Section>

        <Section title="3. Acceptable use">
          <p>You agree not to:</p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>Scrape, crawl, or automate access beyond documented API endpoints</li>
            <li>Resell the service or rebrand it as your own without a separate written agreement</li>
            <li>Use outputs from the service to train a competing AI memory or learning product</li>
            <li>Attempt to probe, test, or reverse-engineer the security of the platform</li>
            <li>Upload content you do not have the right to upload</li>
            <li>Use the service for anything illegal, defamatory, harassing, or that infringes the rights of others</li>
          </ul>
          <p className="mt-3">
            The SDK itself is AGPL-3.0; the AGPL governs what you can do with that source code. These
            terms govern the hosted service, not your use of the open source code.
          </p>
        </Section>

        <Section title="4. Plans and billing">
          <p>Paid plans are billed by Stripe. The current tiers are:</p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li><strong>Free</strong> — limited usage; no card required</li>
            <li><strong>Cloud</strong> — $29 per month, billed monthly</li>
            <li><strong>Team</strong> — $99 per month, billed monthly</li>
            <li><strong>Enterprise</strong> — custom pricing, contact us</li>
          </ul>
          <p className="mt-3">
            Subscriptions renew automatically until canceled. You can cancel at any time from the
            dashboard billing page; your plan continues until the end of the paid period and does not
            renew after that. <strong>We do not issue prorated refunds</strong> for unused time inside
            a billing period. If a charge is made in error, email{' '}
            <EmailLink>support@gradata.ai</EmailLink> and we will investigate.
          </p>
          <p className="mt-3">
            Prices are in US dollars and do not include taxes. You are responsible for any sales tax,
            VAT, or similar taxes that apply where you are.
          </p>
          <p className="mt-3">
            We may change prices. We will give you at least 30 days notice by email before a price
            change takes effect on your plan. If you do not accept the change, you can cancel before
            it takes effect.
          </p>
        </Section>

        <Section title="5. API rate limits and fair use">
          <p>
            Be reasonable with API usage. If your workload starts to affect other customers we may
            throttle your requests, contact you to discuss a higher tier, or in extreme cases suspend
            service. We will reach out before taking the last step whenever practical.
          </p>
        </Section>

        <Section title="6. Intellectual property">
          <p>
            <strong>You own your data.</strong> The synthesized principles, metrics, and any outputs
            derived from your corrections are yours. You grant us a limited license to process that
            data so that we can operate the service for you.
          </p>
          <p className="mt-3">
            <strong>We own the platform.</strong> The cloud dashboard, backend API, graduation engine,
            and all associated branding and know-how are ours. The SDK source code is licensed to you
            separately under the AGPL-3.0; its license terms live in the{' '}
            <a
              href="https://github.com/gradata-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--color-accent-blue)] underline-offset-4 hover:underline"
            >
              public repository
            </a>
            .
          </p>
          <p className="mt-3">
            If you submit feedback or suggestions, we may use them without obligation. We will not
            identify you as the source without your permission.
          </p>
        </Section>

        <Section title="7. Termination">
          <p>
            You can terminate your account at any time by canceling from the dashboard and emailing{' '}
            <EmailLink>support@gradata.ai</EmailLink> to request deletion.
          </p>
          <p className="mt-3">
            We can terminate or suspend your account if you violate these terms, if we are legally
            required to, or if your account is inactive for an extended period. For non-cause
            termination of a paying account, we will give at least 30 days notice so you can export
            your data.
          </p>
          <p className="mt-3">
            On termination, sections 6 (intellectual property), 8 (disclaimers), 9 (limitation of
            liability), 10 (indemnification), and 12 (governing law) survive.
          </p>
        </Section>

        <Section title="8. Disclaimer of warranties">
          <p>
            The service is provided <strong>&ldquo;as is&rdquo;</strong> and <strong>&ldquo;as
            available&rdquo;</strong>. To the maximum extent permitted by law, we disclaim all
            warranties, whether express, implied, statutory, or otherwise, including warranties of
            merchantability, fitness for a particular purpose, non-infringement, and any warranty that
            the service will be uninterrupted, error-free, or that learned principles will be
            accurate.
          </p>
        </Section>

        <Section title="9. Limitation of liability">
          <p>
            To the maximum extent permitted by law, our total liability arising out of or related to
            these terms or the service is <strong>capped at the fees you paid to Gradata in the
            twelve (12) months preceding the event giving rise to the claim</strong>. If you are on
            the free plan, that cap is one hundred US dollars.
          </p>
          <p className="mt-3">
            Neither party will be liable for indirect, incidental, special, consequential, or punitive
            damages, lost profits, lost revenue, lost data, or business interruption, even if advised
            of the possibility. Nothing in this section limits liability that cannot be limited under
            applicable law (such as fraud or willful misconduct).
          </p>
        </Section>

        <Section title="10. Indemnification">
          <p>
            You agree to defend and indemnify us against third-party claims arising from your misuse
            of the service, your violation of these terms, or your violation of another party&rsquo;s
            rights. We will defend and indemnify you against third-party claims that your authorized
            use of the service infringes that third party&rsquo;s intellectual property rights. Both
            carve-outs exclude the other party&rsquo;s negligence or willful misconduct. The party
            seeking indemnification must give prompt notice and reasonable cooperation.
          </p>
        </Section>

        <Section title="11. Changes to these terms">
          <p>
            We may update these terms. For material changes, we will email the address on your account
            at least 30 days before the change takes effect. If you keep using the service after the
            effective date, you accept the updated terms. If you do not accept them, you can cancel
            before they take effect.
          </p>
        </Section>

        <Section title="12. Governing law and disputes">
          <p>
            These terms are governed by the laws of the State of Delaware, United States, without
            regard to its conflict of laws principles. Exclusive jurisdiction and venue for any
            dispute lies in the state and federal courts located in Delaware, and both parties consent
            to that jurisdiction. If you are a consumer in a jurisdiction that grants you the right to
            sue in your home country, nothing in this section removes that right.
          </p>
        </Section>

        <Section title="13. Miscellaneous">
          <p>
            These terms, together with the Privacy Policy and any order form, are the entire agreement
            between you and us about the service. If any part is unenforceable, the rest stays in
            effect. Failure to enforce a term is not a waiver. You cannot assign these terms without
            our written consent; we can assign them to an affiliate or to a buyer of substantially all
            of our assets.
          </p>
        </Section>

        <Section title="14. Contact">
          <p>
            Legal notices: <EmailLink>legal@gradata.ai</EmailLink>. Everything else:{' '}
            <EmailLink>support@gradata.ai</EmailLink>.
          </p>
        </Section>

        <footer className="mt-12 flex items-center justify-between border-t border-[var(--color-border)] pt-6 text-[12px] text-[var(--color-body)]">
          <Link href="/" className="font-mono uppercase tracking-wider hover:text-[var(--color-accent-blue)]">
            ← Back to Gradata
          </Link>
          <Link href="/legal/privacy" className="font-mono uppercase tracking-wider hover:text-[var(--color-accent-blue)]">
            Privacy Policy →
          </Link>
        </footer>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <GlassCard>
        <h2 className="mb-3 text-[18px]">{title}</h2>
        <div className="space-y-2 text-[14px] leading-relaxed text-[var(--color-body)]">
          {children}
        </div>
      </GlassCard>
    </section>
  )
}

function EmailLink({ children }: { children: string }) {
  return (
    <a
      href={`mailto:${children}`}
      className="text-[var(--color-accent-blue)] underline-offset-4 hover:underline"
    >
      {children}
    </a>
  )
}

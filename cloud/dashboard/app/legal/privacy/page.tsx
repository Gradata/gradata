import Link from 'next/link'
import type { Metadata } from 'next'
import { GlassCard } from '@/components/layout/GlassCard'

export const metadata: Metadata = {
  title: 'Privacy Policy — Gradata',
  description:
    'How Gradata handles data: what stays local, what reaches the cloud, who we share with, and how to exercise your rights.',
}

const LAST_UPDATED = '2026-04-13'

export default function PrivacyPolicyPage() {
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
          <h1 className="mt-4 text-[32px] leading-tight md:text-[40px]">Privacy Policy</h1>
          <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-[var(--color-body)]">
            Last updated {LAST_UPDATED}
          </p>
        </header>

        <GlassCard gradTop className="mb-6">
          <p className="text-[14px] leading-relaxed text-[var(--color-body)]">
            Gradata is an AI memory layer that learns from the corrections you make. This policy explains
            what data our cloud service (app.gradata.ai and api.gradata.ai) collects, what it never
            collects, where that data lives, and how you control it. We write in plain English on
            purpose.
          </p>
        </GlassCard>

        <Section title="1. What we collect">
          <p>
            When you create an account and use the cloud dashboard, we collect:
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>
              <strong>Account data.</strong> Email address and an optional display name from Supabase
              Auth. If you later sign in with Google, we receive the name and email on that Google
              profile.
            </li>
            <li>
              <strong>Synthesized principles.</strong> The distilled rule text the SDK produces after
              corrections graduate. These are short, declarative statements (for example, <em>never
              use em dashes in emails</em>). The raw correction body is not part of this.
            </li>
            <li>
              <strong>Aggregate metrics.</strong> Counters and timestamps the SDK uploads so the
              graduation engine can reason about recency: correction counts, graduation counts, fire
              counts, session IDs, and session timestamps. Numbers and IDs, not content.
            </li>
            <li>
              <strong>Billing metadata.</strong> If you subscribe, Stripe creates a customer record and
              a subscription record. We store the Stripe customer ID, plan tier, and subscription
              status. We do not see or store card numbers or CVCs — Stripe handles payment details
              directly.
            </li>
            <li>
              <strong>Error events.</strong> When something breaks in the backend or dashboard, Sentry
              receives a stack trace and the minimum metadata needed to fix it. See section 3 for the
              scrubbing rules.
            </li>
          </ul>
        </Section>

        <Section title="2. What we do not collect">
          <p>The architecture is local-first. The following never leaves your device:</p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>
              <strong>Raw correction text.</strong> Your diffs, drafts, and edits stay in the local
              brain file on your machine. Only the synthesized principle is uploaded.
            </li>
            <li>
              <strong>Draft or final content.</strong> The SDK strips draft and final previews before
              any upload.
            </li>
            <li>
              <strong>Local files or source code.</strong> Gradata does not read or transmit the
              project files you run it against.
            </li>
            <li>
              <strong>IP addresses.</strong> Sentry is configured with <code className="font-mono text-[12px]">send_default_pii=false</code>,
              so IPs and usernames are stripped from error events. Cloudflare, our CDN, may record
              request IPs in its own edge logs under its privacy policy; we do not receive or store
              them ourselves.
            </li>
            <li>
              <strong>Tracking cookies.</strong> We set an auth session cookie and nothing else. No
              advertising pixels, no third-party analytics cookies, no fingerprinting.
            </li>
          </ul>
        </Section>

        <Section title="3. Error tracking details">
          <p>Sentry is disabled unless a DSN is configured. When it is on, it drops:</p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>Request bodies (these can contain Stripe customer emails or webhook payloads)</li>
            <li>Cookies, <code className="font-mono text-[12px]">Authorization</code> headers, <code className="font-mono text-[12px]">X-API-Key</code>, and <code className="font-mono text-[12px]">X-Stripe-Signature</code> headers</li>
            <li>Service role keys, webhook secrets, access tokens, and refresh tokens anywhere in the event</li>
            <li>IP addresses and usernames</li>
            <li>Local variables in stack frames</li>
          </ul>
          <p className="mt-3">
            Session replay captures on error only and masks all text content.
          </p>
        </Section>

        <Section title="4. Where your data lives">
          <p>
            Your data is processed by a small set of vendors (sub-processors). Each is linked to their
            own privacy policy.
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>
              <strong>Supabase</strong> — Postgres database and authentication, hosted in a US region by
              default. Stores account, workspace, brain, principle, metric, and billing metadata rows.{' '}
              <ExtLink href="https://supabase.com/privacy">supabase.com/privacy</ExtLink>
            </li>
            <li>
              <strong>Stripe</strong> — subscription billing and payment processing. PCI-compliant.
              Receives the minimum billing metadata needed to charge and invoice.{' '}
              <ExtLink href="https://stripe.com/privacy">stripe.com/privacy</ExtLink>
            </li>
            <li>
              <strong>Cloudflare</strong> — CDN and edge network for the dashboard. May retain edge
              request logs per its policy.{' '}
              <ExtLink href="https://www.cloudflare.com/privacypolicy/">cloudflare.com/privacypolicy</ExtLink>
            </li>
            <li>
              <strong>Sentry</strong> — error and performance event storage. Only receives scrubbed
              events as described in section 3.{' '}
              <ExtLink href="https://sentry.io/privacy/">sentry.io/privacy</ExtLink>
            </li>
            <li>
              <strong>Google</strong> — only if you choose to sign in with Google OAuth. We receive
              your Google profile email and name.{' '}
              <ExtLink href="https://policies.google.com/privacy">policies.google.com/privacy</ExtLink>
            </li>
          </ul>
          <p className="mt-3">
            We do not sell personal data, and we do not share it with advertising networks.
          </p>
        </Section>

        <Section title="5. Security">
          <p>
            Traffic between your SDK, the dashboard, and our API is served over TLS 1.2 or higher.
            Supabase enforces row-level security so every dashboard query is scoped to the signed-in
            user. Service role keys are only held by the backend, never exposed to the browser. Stripe
            processes card data; we never see or store PANs or CVCs.
          </p>
          <p className="mt-3">
            No system is unbreakable. We avoid marketing superlatives like &ldquo;military-grade&rdquo; or
            &ldquo;unhackable&rdquo; because they are not meaningful claims.
          </p>
        </Section>

        <Section title="6. Retention">
          <p>
            We retain account, principle, and metric data while your account is active. After you
            delete your account, we delete your personal records within 30 days. Aggregate metrics may
            be retained in anonymized form for product analytics. Stripe retains billing records for as
            long as required by its own policies and applicable financial regulations.
          </p>
          <p className="mt-3">
            Error events in Sentry expire according to Sentry&rsquo;s standard retention (typically 30
            or 90 days depending on plan).
          </p>
        </Section>

        <Section title="7. Your rights">
          <p>You can:</p>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>
              <strong>Access or export</strong> the data we hold about you. Email{' '}
              <EmailLink>support@gradata.ai</EmailLink> and we will return a copy within 30 days.
            </li>
            <li>
              <strong>Correct</strong> inaccurate account data from the dashboard settings page or by
              email.
            </li>
            <li>
              <strong>Delete</strong> your account and associated cloud data. Email{' '}
              <EmailLink>support@gradata.ai</EmailLink> or use the dashboard account page. Raw
              corrections on your device are deleted when you remove the local brain file.
            </li>
            <li>
              <strong>Object or restrict</strong> processing where GDPR, UK GDPR, or similar laws apply
              to you. Contact us and we will comply within the statutory timeframe.
            </li>
          </ul>
        </Section>

        <Section title="8. Children">
          <p>
            Gradata is not designed for and is not directed at anyone under the age of 16. If you
            believe a child has created an account, email{' '}
            <EmailLink>support@gradata.ai</EmailLink> and we will remove it.
          </p>
        </Section>

        <Section title="9. International transfers">
          <p>
            Our primary Supabase region is in the United States. If you are in the EU, UK, or another
            region with specific data transfer rules, using Gradata constitutes consent to transfer of
            your data to the US under standard contractual clauses where required.
          </p>
        </Section>

        <Section title="10. Changes to this policy">
          <p>
            If we make material changes, we will email the address on your account at least 30 days
            before they take effect, and we will update the &ldquo;Last updated&rdquo; date at the top
            of this page. Non-material clarifications may land without a separate notice.
          </p>
        </Section>

        <Section title="11. Contact">
          <p>
            Questions, data requests, or privacy concerns:{' '}
            <EmailLink>support@gradata.ai</EmailLink>. For legal notices specifically:{' '}
            <EmailLink>legal@gradata.ai</EmailLink>.
          </p>
        </Section>

        <footer className="mt-12 flex items-center justify-between border-t border-[var(--color-border)] pt-6 text-[12px] text-[var(--color-body)]">
          <Link href="/" className="font-mono uppercase tracking-wider hover:text-[var(--color-accent-blue)]">
            ← Back to Gradata
          </Link>
          <Link href="/legal/terms" className="font-mono uppercase tracking-wider hover:text-[var(--color-accent-blue)]">
            Terms of Service →
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

function ExtLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--color-accent-blue)] underline-offset-4 hover:underline"
    >
      {children}
    </a>
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

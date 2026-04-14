import type { ReactNode } from "react";

type LegalPageHeaderProps = {
  title: string;
  lastUpdated: string;
  /** Appended after ``lastUpdated`` behind a middle-dot separator. */
  status?: string;
  /** Draft-review banner shown below the header. Render ``null`` for none. */
  banner?: ReactNode;
};

/**
 * Shared header + draft banner for legal pages (DPA, SLA, subprocessors).
 * Keeps the "Legal / h1 / last updated" pattern in one place so copy tweaks
 * (e.g. swapping "DRAFT" to "signed-off") stay consistent across the suite.
 */
export function LegalPageHeader({
  title,
  lastUpdated,
  status,
  banner,
}: LegalPageHeaderProps) {
  return (
    <>
      <header className="mb-10">
        <div className="mb-4 text-xs uppercase tracking-widest text-[color:var(--color-muted-foreground)]">
          Legal
        </div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-3 text-sm text-[color:var(--color-muted-foreground)]">
          Last updated: {lastUpdated}
          {status ? <> &middot; {status}</> : null}
        </p>
      </header>
      {banner}
    </>
  );
}

/**
 * Standard "draft — pending legal review" banner. Separate component so a
 * page can render the header without a banner (once legal signs off, just
 * drop the ``banner`` prop).
 */
export function LegalDraftBanner({ children }: { children: ReactNode }) {
  return (
    <section className="mb-6 rounded border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-200/90">
      {children}
    </section>
  );
}

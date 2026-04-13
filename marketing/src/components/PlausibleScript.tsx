import Script from "next/script";
import { analyticsEnabled, plausibleDomain } from "@/lib/analytics";

/**
 * Renders the Plausible script tag only when NEXT_PUBLIC_ENABLE_ANALYTICS=true.
 *
 * We also attach a tiny shim so track() calls queued before the real script
 * loads are still delivered. Plausible's official script installs the same
 * shim, but we add one defensively in case of race conditions during hydration.
 */
export function PlausibleScript() {
  if (!analyticsEnabled()) return null;
  const domain = plausibleDomain();
  return (
    <>
      <Script
        strategy="afterInteractive"
        defer
        data-domain={domain}
        src="https://plausible.io/js/script.tagged-events.js"
      />
      <Script id="plausible-shim" strategy="afterInteractive">
        {`window.plausible = window.plausible || function() { (window.plausible.q = window.plausible.q || []).push(arguments) }`}
      </Script>
    </>
  );
}

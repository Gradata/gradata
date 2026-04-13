/**
 * Privacy-first analytics helper (Plausible).
 *
 * Gates all event firing on NEXT_PUBLIC_ENABLE_ANALYTICS=true so local dev
 * and preview builds stay silent. Respects DNT by default (Plausible's
 * script honors DNT when configured; we also short-circuit client-side).
 *
 * Tracked events (see docs at marketing/.env.example):
 *   signup_click, signup_complete, docs_click, install_copy
 */

declare global {
  interface Window {
    plausible?: (
      event: string,
      options?: { props?: Record<string, string | number | boolean> },
    ) => void;
  }
}

/** True only when NEXT_PUBLIC_ENABLE_ANALYTICS === "true". */
export function analyticsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === "true";
}

/**
 * Respect browser Do-Not-Track even if Plausible's server-side DNT handling
 * is off. Defensive — we'd rather under-track than over-track.
 */
function dntOn(): boolean {
  if (typeof navigator === "undefined") return false;
  const n = navigator as Navigator & { msDoNotTrack?: string; doNotTrack?: string };
  const w = typeof window !== "undefined" ? (window as unknown as { doNotTrack?: string }) : undefined;
  const raw = n.doNotTrack ?? w?.doNotTrack ?? n.msDoNotTrack;
  return raw === "1" || raw === "yes";
}

export type AnalyticsEvent =
  | "signup_click"
  | "signup_complete"
  | "docs_click"
  | "install_copy";

/**
 * Fire a named event to Plausible. No-op if analytics is disabled,
 * DNT is on, or the plausible() function hasn't loaded yet.
 */
export function track(
  event: AnalyticsEvent,
  props?: Record<string, string | number | boolean>,
): void {
  if (!analyticsEnabled()) return;
  if (typeof window === "undefined") return;
  if (dntOn()) return;
  if (typeof window.plausible !== "function") return;
  try {
    window.plausible(event, props ? { props } : undefined);
  } catch {
    // Analytics must never break the app.
  }
}

/**
 * Domain used for Plausible script + API. Defaults to gradata.ai.
 * Override with NEXT_PUBLIC_PLAUSIBLE_DOMAIN.
 */
export function plausibleDomain(): string {
  return process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN || "gradata.ai";
}

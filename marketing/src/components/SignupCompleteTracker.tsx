"use client";

import { useEffect } from "react";
import { track } from "@/lib/analytics";

/**
 * Fires `signup_complete` exactly once per redirect back from Supabase.
 *
 * Supabase redirects to https://gradata.ai/?signup=success on successful
 * email confirmation. We read the query string, fire the event, then strip
 * the param so a refresh doesn't double-count.
 */
export function SignupCompleteTracker() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (url.searchParams.get("signup") === "success") {
      track("signup_complete");
      url.searchParams.delete("signup");
      window.history.replaceState({}, "", url.toString());
    }
  }, []);
  return null;
}

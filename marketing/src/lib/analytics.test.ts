/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyticsEnabled, plausibleDomain, track } from "./analytics";

const ORIGINAL_ENV = { ...process.env };

function setEnv(key: string, value: string | undefined) {
  if (value === undefined) delete process.env[key];
  else process.env[key] = value;
}

describe("analytics", () => {
  beforeEach(() => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", undefined);
    setEnv("NEXT_PUBLIC_PLAUSIBLE_DOMAIN", undefined);
    // reset window.plausible between tests
    delete (window as unknown as { plausible?: unknown }).plausible;
  });

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
  });

  it("is disabled by default", () => {
    expect(analyticsEnabled()).toBe(false);
  });

  it("is enabled only when env var is exactly 'true'", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    expect(analyticsEnabled()).toBe(true);
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "TRUE");
    expect(analyticsEnabled()).toBe(false);
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "1");
    expect(analyticsEnabled()).toBe(false);
  });

  it("defaults domain to gradata.ai", () => {
    expect(plausibleDomain()).toBe("gradata.ai");
  });

  it("honors custom domain from env", () => {
    setEnv("NEXT_PUBLIC_PLAUSIBLE_DOMAIN", "staging.gradata.ai");
    expect(plausibleDomain()).toBe("staging.gradata.ai");
  });

  it("does not call plausible when analytics disabled", () => {
    const spy = vi.fn();
    (window as unknown as { plausible: unknown }).plausible = spy;
    track("signup_click");
    expect(spy).not.toHaveBeenCalled();
  });

  it("calls plausible with event name when enabled", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    const spy = vi.fn();
    (window as unknown as { plausible: unknown }).plausible = spy;
    track("signup_click");
    expect(spy).toHaveBeenCalledWith("signup_click", undefined);
  });

  it("passes props when supplied", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    const spy = vi.fn();
    (window as unknown as { plausible: unknown }).plausible = spy;
    track("install_copy", { language: "bash" });
    expect(spy).toHaveBeenCalledWith("install_copy", { props: { language: "bash" } });
  });

  it("is a no-op when plausible function not present", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    // plausible absent from window
    expect(() => track("docs_click")).not.toThrow();
  });

  it("respects navigator.doNotTrack", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    const spy = vi.fn();
    (window as unknown as { plausible: unknown }).plausible = spy;
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    try {
      track("signup_click");
      expect(spy).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(navigator, "doNotTrack", { value: null, configurable: true });
    }
  });

  it("swallows exceptions from plausible", () => {
    setEnv("NEXT_PUBLIC_ENABLE_ANALYTICS", "true");
    (window as unknown as { plausible: unknown }).plausible = () => {
      throw new Error("network");
    };
    expect(() => track("signup_complete")).not.toThrow();
  });
});

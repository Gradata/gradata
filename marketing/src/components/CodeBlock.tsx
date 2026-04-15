"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { track } from "@/lib/analytics";

type CodeBlockProps = {
  code: string;
  language?: string;
  className?: string;
  caption?: string;
  /** When true, shows a copy button and fires the `install_copy` event on copy. */
  copyable?: boolean;
  /** When present, the entire copied text is `copyValue` instead of the rendered `code`. */
  copyValue?: string;
  /** Override the aria-label for the copy button. Defaults to "Copy code". */
  copyAriaLabel?: string;
};

export function CodeBlock({
  code,
  language,
  className,
  caption,
  copyable = false,
  copyValue,
  copyAriaLabel = "Copy code",
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current);
        resetTimerRef.current = null;
      }
    };
  }, []);

  const onCopy = async () => {
    try {
      const text = copyValue ?? code;
      await navigator.clipboard.writeText(text);
      track("install_copy", { language: language ?? "text" });
      setCopied(true);
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current);
      }
      resetTimerRef.current = setTimeout(() => {
        setCopied(false);
        resetTimerRef.current = null;
      }, 1500);
    } catch {
      // Clipboard blocked — ignore silently.
    }
  };

  return (
    <figure
      className={cn(
        "overflow-hidden rounded-xl border border-[color:var(--color-border)] bg-[oklch(0.1_0.01_270)]",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-[color:var(--color-border)]/60 px-4 py-2 text-xs text-[color:var(--color-muted-foreground)]">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.55_0.18_25)]" aria-hidden />
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.7_0.15_90)]" aria-hidden />
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.65_0.18_150)]" aria-hidden />
        </div>
        <div className="flex items-center gap-3">
          {language && <span className="font-mono tracking-wide">{language}</span>}
          {copyable && (
            <button
              type="button"
              onClick={onCopy}
              aria-label={copyAriaLabel}
              className="rounded border border-[color:var(--color-border)]/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-muted-foreground)] transition-colors hover:bg-[color:var(--color-card)] hover:text-[color:var(--color-foreground)]"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          )}
        </div>
      </div>
      <pre className="overflow-x-auto px-4 py-4 text-sm leading-relaxed">
        <code className="font-mono text-[color:var(--color-foreground)]">{code}</code>
      </pre>
      {caption && (
        <figcaption className="border-t border-[color:var(--color-border)]/60 px-4 py-2 text-xs text-[color:var(--color-muted-foreground)]">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

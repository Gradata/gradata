import { cn } from "@/lib/cn";

type CodeBlockProps = {
  code: string;
  language?: string;
  className?: string;
  caption?: string;
};

export function CodeBlock({ code, language, className, caption }: CodeBlockProps) {
  return (
    <figure className={cn("overflow-hidden rounded-xl border border-[color:var(--color-border)] bg-[oklch(0.1_0.01_270)]", className)}>
      <div className="flex items-center justify-between border-b border-[color:var(--color-border)]/60 px-4 py-2 text-xs text-[color:var(--color-muted-foreground)]">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.55_0.18_25)]" aria-hidden />
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.7_0.15_90)]" aria-hidden />
          <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.65_0.18_150)]" aria-hidden />
        </div>
        {language && <span className="font-mono tracking-wide">{language}</span>}
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

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type GlassCardProps = {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
};

export function GlassCard({ children, className, as: Tag = "div" }: GlassCardProps) {
  return (
    <Tag
      className={cn(
        "relative rounded-xl border border-[color:var(--color-border)]",
        "bg-[color:var(--color-card)]/60 backdrop-blur-xl",
        "shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset,0_30px_80px_-30px_rgba(0,0,0,0.6)]",
        className
      )}
    >
      {children}
    </Tag>
  );
}

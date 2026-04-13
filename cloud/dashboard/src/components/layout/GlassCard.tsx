import { cn } from '@/lib/utils'
import type { HTMLAttributes, ReactNode } from 'react'

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  /** Show the gradient top line (cards with charts or KPIs) */
  gradTop?: boolean
  /** Show the animated gradient scan-line sweep */
  scanLine?: boolean
}

export function GlassCard({ children, gradTop, scanLine, className, ...rest }: GlassCardProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-[0.625rem] p-6 glass transition-[border-color,transform,box-shadow] duration-300',
        'hover:border-[rgba(58,130,255,0.25)] hover:-translate-y-0.5 hover:shadow-[0_8px_32px_rgba(58,130,255,0.08)]',
        className,
      )}
      {...rest}
    >
      {gradTop && <div className="absolute inset-x-0 top-0 h-px bg-gradient-brand opacity-50" />}
      {scanLine && <span className="scan-line" />}
      {children}
    </div>
  )
}

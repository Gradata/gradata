'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const SECTIONS = [
  {
    label: 'Brain',
    items: [
      { href: '/dashboard', label: 'Overview', icon: '◐' },
      { href: '/corrections', label: 'Corrections', icon: '◷' },
      { href: '/rules', label: 'Latest Rules', icon: '▣' },
      { href: '/meta-rules', label: 'Meta Rules', icon: '◈' },
      { href: '/self-healing', label: 'Self-Healing', icon: '✦' },
      { href: '/observability', label: 'Observability', icon: '◐' },
      { href: '/privacy', label: 'Privacy', icon: '◉' },
      { href: '/setup', label: 'Setup', icon: '⌨' },
      { href: '/docs', label: 'Docs', icon: '◰' },
    ],
  },
  {
    label: 'Team',
    items: [
      { href: '/team', label: 'Overview', icon: '◐' },
      { href: '/team/members', label: 'Members', icon: '◯' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { href: '/billing', label: 'Billing', icon: '▦' },
      { href: '/api-keys', label: 'API Keys', icon: '⌘' },
      { href: '/settings', label: 'Account', icon: '⊙' },
      { href: '/notifications', label: 'Notifications', icon: '◉' },
    ],
  },
  {
    label: 'Operator',
    items: [
      { href: '/operator', label: 'God mode', icon: '✦' },
    ],
  },
] as const

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return (
    <>
      <div className="mb-2 flex items-center gap-2.5 p-3">
        <div className="h-7 w-7 rounded-lg bg-gradient-brand shadow-[0_0_16px_rgba(58,130,255,0.3)]" />
        <div>
          <div className="font-[var(--font-heading)] text-[15px] font-bold text-[var(--color-text)]">gradata</div>
          <div className="text-[11px] text-[var(--color-body)]">fitness for your brain</div>
        </div>
      </div>

      {SECTIONS.map((section) => (
        <div key={section.label}>
          <div className="px-3 pb-1.5 pt-4 text-[10px] font-semibold uppercase tracking-[1.2px] text-[rgba(136,149,167,0.6)]">
            {section.label}
          </div>
          {section.items.map((item) => {
            const active = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  'flex items-center gap-2.5 rounded-[0.5rem] px-3 py-2 text-[13px] transition-all',
                  active
                    ? 'border border-[rgba(58,130,255,0.15)] bg-[rgba(58,130,255,0.12)] text-[var(--color-text)]'
                    : 'text-[var(--color-body)] hover:bg-[rgba(58,130,255,0.08)] hover:text-[var(--color-text)]',
                )}
              >
                <span className="w-4 text-center text-sm opacity-50">{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </div>
      ))}
    </>
  )
}

function Sidebar() {
  return (
    <aside className="hidden md:flex h-screen w-[240px] min-w-[240px] flex-col gap-0.5 overflow-y-auto border-r border-[var(--color-border)] bg-[rgba(12,17,32,0.95)] p-3 backdrop-blur-xl">
      <SidebarContent />
    </aside>
  )
}

function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  // Lock body scroll while drawer is open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [open])

  if (!open) return null

  return (
    <div className="md:hidden fixed inset-0 z-50">
      {/* Overlay */}
      <button
        type="button"
        aria-label="Close menu"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Drawer */}
      <aside className="absolute inset-y-0 left-0 flex h-full w-[260px] max-w-[80vw] flex-col gap-0.5 overflow-y-auto border-r border-[var(--color-border)] bg-[rgba(12,17,32,0.98)] p-3 backdrop-blur-xl">
        <SidebarContent onNavigate={onClose} />
      </aside>
    </div>
  )
}

function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, signOut } = useAuth()
  return (
    <header className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3 md:px-8 md:py-4">
      <div className="flex items-center gap-2 md:hidden">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open menu"
          className="flex h-11 w-11 items-center justify-center rounded-[0.5rem] border border-[var(--color-border)] text-[var(--color-body)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
        >
          {/* Hamburger */}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-md bg-gradient-brand shadow-[0_0_12px_rgba(58,130,255,0.3)]" />
          <span className="font-[var(--font-heading)] text-[14px] font-bold text-[var(--color-text)]">gradata</span>
        </div>
      </div>
      <div className="hidden md:block" />
      {user && (
        <div className="flex items-center gap-2 md:gap-3">
          <span className="hidden sm:inline text-sm text-[var(--color-body)] truncate max-w-[180px] md:max-w-none">{user.email}</span>
          <button
            onClick={() => signOut()}
            className="rounded-[0.5rem] border border-[var(--color-border)] px-3 py-1.5 text-[12px] text-[var(--color-body)] transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
          >
            Sign out
          </button>
        </div>
      )}
    </header>
  )
}

function LegalFooter() {
  return (
    <div className="mt-12 flex items-center justify-center gap-3 font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)] opacity-50">
      <Link
        href="/legal/privacy"
        className="transition-colors hover:text-[var(--color-accent-blue)] hover:opacity-100"
      >
        Privacy
      </Link>
      <span aria-hidden>·</span>
      <Link
        href="/legal/terms"
        className="transition-colors hover:text-[var(--color-accent-blue)] hover:opacity-100"
      >
        Terms
      </Link>
      <span aria-hidden>·</span>
      <span>© 2026 Gradata</span>
    </div>
  )
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'https://api.gradata.ai/api/v1'

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  // Send one heartbeat per dashboard session so "last activity" on the
  // marketing site reflects real users tapping around.
  useEffect(() => {
    fetch(`${API_BASE}/public/heartbeat?source=dashboard`, { method: 'POST' }).catch(() => {})
  }, [])
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="mx-auto max-w-[1280px]">
            {children}
            <LegalFooter />
          </div>
        </main>
      </div>
    </div>
  )
}

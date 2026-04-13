'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
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
      { href: '/settings', label: 'Security', icon: '⊙' },
      { href: '/notifications', label: 'Notifications', icon: '◉' },
    ],
  },
] as const

function Sidebar() {
  const pathname = usePathname()
  return (
    <aside className="flex h-screen w-[240px] min-w-[240px] flex-col gap-0.5 overflow-y-auto border-r border-[var(--color-border)] bg-[rgba(12,17,32,0.95)] p-3 backdrop-blur-xl">
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
    </aside>
  )
}

function Header() {
  const { user, signOut } = useAuth()
  return (
    <header className="flex items-center justify-between border-b border-[var(--color-border)] px-8 py-4">
      <div />
      {user && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-[var(--color-body)]">{user.email}</span>
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

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-8">
          <div className="mx-auto max-w-[1280px]">{children}</div>
        </main>
      </div>
    </div>
  )
}

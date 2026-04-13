'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'

export default function Home() {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (loading) return
    router.replace(user ? '/dashboard' : '/login')
  }, [user, loading, router])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-3 font-mono text-[12px] text-[var(--color-body)]">
        <span className="h-6 w-6 animate-pulse rounded-lg bg-gradient-brand shadow-[0_0_16px_rgba(58,130,255,0.3)]" />
        <span>gradata</span>
      </div>
    </div>
  )
}

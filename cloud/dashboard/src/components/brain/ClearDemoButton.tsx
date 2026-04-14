'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import api from '@/lib/api'
import { readApiError } from '@/lib/errors'
import type { ClearDemoResponse } from '@/types/api'

interface Props {
  brainId: string
  /** Called after a successful clear so the parent can refetch. */
  onCleared?: (result: ClearDemoResponse) => void
}

export function ClearDemoButton({ brainId, onCleared }: Props) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ClearDemoResponse | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up any pending close/redirect timer on unmount so navigating away
  // during the success banner delay can't force-navigate a different page.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleConfirm = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<ClearDemoResponse>(`/brains/${brainId}/clear-demo`)
      setResult(res.data)
      onCleared?.(res.data)
      // If the brain row itself was deleted (seeded demo brain), redirect to
      // the brains list instead of reloading this page — reloading would land
      // the user on the "Brain not found" state.
      const brainDeleted = (res.data.by_table?.brains ?? 0) > 0
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        setOpen(false)
        setResult(null)
        if (brainDeleted) {
          router.push('/dashboard')
        } else if (typeof window !== 'undefined') {
          // Non-destructive refresh so every card reflects the cleared state.
          window.location.reload()
        }
      }, 900)
    } catch (err) {
      setError(readApiError(err, 'Could not clear demo data. Try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button
        variant="outline"
        onClick={() => { setError(null); setResult(null); setOpen(true) }}
        className="text-[var(--color-destructive)] hover:text-[var(--color-destructive)]"
      >
        Remove demo data
      </Button>

      <Dialog open={open} onOpenChange={(next) => !busy && setOpen(next)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove demo data?</DialogTitle>
            <DialogDescription>
              This deletes every seeded demo lesson, correction, event, and meta-rule for this brain.
              Your real data is left untouched. If the brain itself was seeded as a demo, it will be
              removed too.
            </DialogDescription>
          </DialogHeader>

          {error && (
            <p className="rounded-md border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/10 px-3 py-2 text-sm text-[var(--color-destructive)]">
              {error}
            </p>
          )}

          {result && (
            <p className="rounded-md bg-[rgba(34,197,94,0.1)] px-3 py-2 text-sm text-[var(--color-success)]">
              Removed {result.deleted} demo row{result.deleted === 1 ? '' : 's'}. Refreshing…
            </p>
          )}

          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={busy || result !== null}
              className="bg-[var(--color-destructive)] text-white hover:bg-[var(--color-destructive)]/90"
            >
              {busy ? 'Removing…' : 'Remove demo data'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

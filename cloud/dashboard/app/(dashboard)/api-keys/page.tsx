'use client'

import { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { GlassCard } from '@/components/layout/GlassCard'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { useApi } from '@/hooks/useApi'
import api from '@/lib/api'
import type { ApiKey, ApiKeyCreateResponse } from '@/types/api'

export default function ApiKeysPage() {
  const { data: keys, loading, error, refetch } = useApi<ApiKey[]>('/api-keys')
  const [showCreate, setShowCreate] = useState(false)
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null)
  const [keyName, setKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const handleCreate = useCallback(async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const res = await api.post<ApiKeyCreateResponse>('/api-keys', {
        name: keyName || 'Default',
      })
      setNewKey(res.data)
      setKeyName('')
      refetch()
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail ?? 'Could not generate key.')
    } finally {
      setCreating(false)
    }
  }, [keyName, refetch])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.delete(`/api-keys/${id}`)
      refetch()
    } catch {
      // interceptor handles
    }
  }, [refetch])

  const handleCopy = useCallback(() => {
    if (newKey) {
      navigator.clipboard.writeText(newKey.key)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [newKey])

  if (loading) return <LoadingSpinner className="py-20" />
  if (error) return <ErrorState message={error} onRetry={refetch} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px]">API Keys</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Manage keys for the Gradata SDK
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Generate New Key</Button>
      </div>

      {!keys?.length ? (
        <EmptyState
          title="No API keys"
          description="Generate a key to connect your SDK. Keys are shown once; store them securely."
        />
      ) : (
        <GlassCard gradTop>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Last used</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((k) => (
                <TableRow key={k.id}>
                  <TableCell className="font-medium">{k.name}</TableCell>
                  <TableCell className="font-mono text-[12px] text-[var(--color-body)]">
                    gd_{k.key_prefix}…
                  </TableCell>
                  <TableCell className="text-[12px]">
                    {new Date(k.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-[12px] text-[var(--color-body)]">
                    {k.last_used ? new Date(k.last_used).toLocaleDateString() : 'Never'}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-[var(--color-destructive)] hover:text-[var(--color-destructive)]"
                      onClick={() => handleDelete(k.id)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </GlassCard>
      )}

      <Dialog open={showCreate && !newKey} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate API Key</DialogTitle>
            <DialogDescription>
              Give your key a name so you can identify it later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            {createError && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {createError}
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="keyName">Key name</Label>
              <Input
                id="keyName"
                placeholder="e.g. Production"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
              />
            </div>
            <Button onClick={handleCreate} disabled={creating} className="w-full">
              {creating ? 'Generating...' : 'Generate'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!newKey} onOpenChange={() => setNewKey(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Your API Key</DialogTitle>
            <DialogDescription>
              Copy this key now. You will not be able to see it again.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-[0.5rem] border border-[var(--color-border)] bg-black/40 p-3">
            <div className="mb-1 font-mono text-[10px] uppercase text-[var(--color-body)]">
              {newKey?.name}
            </div>
            <code className="block break-all font-mono text-[12px]">{newKey?.key}</code>
          </div>
          <Button onClick={handleCopy} className="w-full">
            {copied ? 'Copied!' : 'Copy to clipboard'}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}

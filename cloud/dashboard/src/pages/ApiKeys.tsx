import { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { useApi } from '@/hooks/useApi'
import api from '@/lib/api'
import type { ApiKey, ApiKeyCreateResponse } from '@/types/api'

export function ApiKeys() {
  const { data: keys, loading, error, refetch } = useApi<ApiKey[]>('/api-keys')
  const [showCreate, setShowCreate] = useState(false)
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null)
  const [keyName, setKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCreate = useCallback(async () => {
    setCreating(true)
    try {
      const res = await api.post<ApiKeyCreateResponse>('/api-keys', {
        name: keyName || 'Default',
      })
      setNewKey(res.data)
      setKeyName('')
      refetch()
    } catch {
      // Error handled by interceptor
    } finally {
      setCreating(false)
    }
  }, [keyName, refetch])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.delete(`/api-keys/${id}`)
      refetch()
    } catch {
      // Error handled by interceptor
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
          <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage keys for the Gradata SDK
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Generate New Key</Button>
      </div>

      {!keys?.length ? (
        <EmptyState
          title="No API keys"
          description="Generate a key to connect your SDK."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Last Used</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      ****{k.key_prefix}
                    </TableCell>
                    <TableCell className="text-sm">
                      {new Date(k.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {k.last_used ? new Date(k.last_used).toLocaleDateString() : 'Never'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(k.id)}
                      >
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreate && !newKey} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate API Key</DialogTitle>
            <DialogDescription>
              Give your key a name so you can identify it later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
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

      {/* Show Key Dialog */}
      <Dialog open={!!newKey} onOpenChange={() => setNewKey(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Your API Key</DialogTitle>
            <DialogDescription>
              Copy this key now. You will not be able to see it again.
            </DialogDescription>
          </DialogHeader>
          <Card className="bg-muted">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground">{newKey?.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <code className="block break-all text-sm">{newKey?.key}</code>
            </CardContent>
          </Card>
          <Button onClick={handleCopy} className="w-full">
            {copied ? 'Copied!' : 'Copy to clipboard'}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}

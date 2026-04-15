'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { isOperatorEmail } from '@/lib/operator'
import { useApi } from '@/hooks/useApi'
import api from '@/lib/api'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'

type Role = 'owner' | 'admin' | 'member'

interface Member {
  user_id: string
  email: string | null
  display_name: string | null
  role: Role | string
  joined_at: string | null
  last_sync_at: string | null
}

const ROLE_BADGE: Record<Role, string> = {
  owner:  'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  admin:  'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  member: 'bg-white/[0.06] text-[var(--color-body)]',
}

export default function TeamMembersPage() {
  const { data: profile, loading: loadingProfile } = useApi<UserProfile>('/users/me')
  const workspaceId = profile?.workspaces?.[0]?.id ?? null
  const myRole = (profile?.workspaces?.[0]?.role as Role | null) ?? 'member'
  const canAdmin = myRole === 'owner' || myRole === 'admin'

  const { data: members, loading: loadingMembers, refetch } = useApi<Member[]>(
    workspaceId ? `/workspaces/${workspaceId}/members` : null,
  )

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member')
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  if (loadingProfile) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier
  const memberList: Member[] = members ?? []

  const handleInvite = async () => {
    if (!workspaceId) return
    setInviting(true)
    setInviteError(null)
    setInviteStatus(null)
    try {
      await api.post(`/workspaces/${workspaceId}/invites`, {
        email: inviteEmail,
        role: inviteRole,
      })
      setInviteStatus(`Invite sent to ${inviteEmail}`)
      setInviteEmail('')
      refetch()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invite failed'
      setInviteError(msg)
    } finally {
      setInviting(false)
    }
  }

  const handleRemove = async (userId: string) => {
    if (!workspaceId) return
    setRemoving(userId)
    try {
      await api.delete(`/workspaces/${workspaceId}/members/${userId}`)
      refetch()
    } finally {
      setRemoving(null)
    }
  }

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Members</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Invite teammates and manage roles
          </p>
        </div>
        {canAdmin && (
          <Button onClick={() => { setInviteOpen(true); setInviteStatus(null); setInviteError(null) }}>
            Invite member
          </Button>
        )}
      </header>

      <PlanGate current={currentPlan} requires="team" featureName="Team member management" bypass={isOperatorEmail(profile?.email)}>
        <GlassCard gradTop>
          {loadingMembers ? (
            <LoadingSpinner className="py-10" />
          ) : memberList.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-[13px] text-[var(--color-body)]">
                No members yet. {canAdmin && 'Invite your first teammate above.'}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {memberList.map((m) => (
                <li key={m.user_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0 sm:flex-nowrap">
                  <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                    <div className="flex flex-wrap items-baseline gap-2.5">
                      <span className="text-[13px] font-medium">
                        {m.display_name || m.email || m.user_id.slice(0, 8)}
                      </span>
                      <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${ROLE_BADGE[(m.role as Role) || 'member']}`}>
                        {m.role}
                      </span>
                    </div>
                    {m.email && m.display_name && (
                      <div className="font-mono text-[10px] text-[var(--color-body)] truncate">{m.email}</div>
                    )}
                  </div>
                  <div className="font-mono text-[11px] text-[var(--color-body)] sm:w-32 sm:text-right">
                    {m.last_sync_at ? `synced ${formatAgo(m.last_sync_at)}` : 'never synced'}
                  </div>
                  {canAdmin && m.role !== 'owner' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={removing === m.user_id}
                      onClick={() => handleRemove(m.user_id)}
                      className="ml-auto text-[var(--color-destructive)] hover:text-[var(--color-destructive)] sm:ml-0"
                    >
                      {removing === m.user_id ? 'Removing…' : 'Remove'}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      </PlanGate>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite a teammate</DialogTitle>
            <DialogDescription>
              They&apos;ll get an email with a sign-up link scoped to this workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            {inviteStatus && (
              <p className="rounded-md bg-[rgba(34,197,94,0.1)] px-3 py-2 text-sm text-[var(--color-success)]">
                {inviteStatus}
              </p>
            )}
            {inviteError && (
              <p className="rounded-md bg-[rgba(239,68,68,0.1)] px-3 py-2 text-sm text-[var(--color-destructive)]">
                {inviteError}
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="inviteEmail">Email</Label>
              <Input id="inviteEmail" type="email" placeholder="teammate@company.com"
                value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inviteRole">Role</Label>
              <select
                id="inviteRole"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member')}
                className="w-full rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-3 py-2 text-sm"
              >
                <option value="member">Member — see own brain only</option>
                <option value="admin">Admin — manage team + settings</option>
              </select>
            </div>
            <Button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail || !workspaceId}
              className="w-full"
            >
              {inviting ? 'Sending…' : 'Send invite'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function formatAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return `${Math.floor(diffMs / 60_000)}m ago`
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

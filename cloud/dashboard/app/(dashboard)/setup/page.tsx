'use client'

import { useState, useMemo } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { useApi } from '@/hooks/useApi'
import type { ApiKey, Brain } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'

/**
 * SDK/MCP setup wizard. Per SIM_B §4: CLI-first distribution, dashboard
 * is a "read-only lens" — this page guides the user through the actual
 * install + first-run flow.
 *
 * Flow:
 * 1. pip install gradata
 * 2. Create API key (button → api-keys page)
 * 3. Initialize brain with snippet
 * 4. Run first session + see it appear
 */
export default function SetupPage() {
  const { data: keys, loading: loadingKeys } = useApi<ApiKey[]>('/api-keys')
  const { data: brains, loading: loadingBrains } = useApi<Brain[]>('/brains')
  const [copied, setCopied] = useState<string | null>(null)

  const hasKey = !!keys?.length
  const hasBrain = !!brains?.length
  const firstKeyPrefix = keys?.[0]?.key_prefix

  const initSnippet = useMemo(() => {
    const key = firstKeyPrefix ? `gd_${firstKeyPrefix}...` : 'gd_YOUR_API_KEY_HERE'
    return `import gradata

brain = gradata.Brain.init(
    name="my-first-brain",
    domain="engineering",
    api_key="${key}",
)

with brain.session() as s:
    response = s.ask("What is a good name for an AI memory tool?")
    print(response)

brain.end_session()
`
  }, [firstKeyPrefix])

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(null), 1500)
  }

  if (loadingKeys || loadingBrains) return <LoadingSpinner className="py-20" />

  const steps: Array<{
    n: number
    title: string
    done: boolean
    body: React.ReactNode
  }> = [
    {
      n: 1,
      title: 'Install the SDK',
      done: true, // we can't detect this, assume done
      body: (
        <CodeBlock code="pip install gradata" onCopy={() => copy('pip install gradata', 'install')} copied={copied === 'install'} />
      ),
    },
    {
      n: 2,
      title: 'Create an API key',
      done: hasKey,
      body: hasKey ? (
        <p className="text-[12px] text-[var(--color-body)]">
          You have {keys?.length} key{keys?.length === 1 ? '' : 's'}. Manage them on the{' '}
          <a href="/api-keys" className="text-[var(--color-accent-blue)] underline">API Keys</a> page.
        </p>
      ) : (
        <a href="/api-keys" className="inline-block">
          <Button>Generate API Key</Button>
        </a>
      ),
    },
    {
      n: 3,
      title: 'Initialize your first brain',
      done: hasBrain,
      body: (
        <CodeBlock
          code={initSnippet}
          onCopy={() => copy(initSnippet, 'init')}
          copied={copied === 'init'}
          language="python"
        />
      ),
    },
    {
      n: 4,
      title: 'Run a session and watch your dashboard',
      done: hasBrain,
      body: (
        <p className="text-[13px] text-[var(--color-body)]">
          The SDK streams correction events to{' '}
          <code className="font-mono text-[var(--color-accent-blue)]">api.gradata.ai</code> at{' '}
          <code className="font-mono">end_session()</code>. Your{' '}
          <a href="/dashboard" className="text-[var(--color-accent-blue)] underline">Overview</a>{' '}
          updates within 30 seconds.
        </p>
      ),
    },
  ]

  const doneCount = steps.filter((s) => s.done).length

  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Setup</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Get your first brain running in under 2 minutes · {doneCount}/{steps.length} complete
        </p>
      </header>

      {/* Progress */}
      <div className="mb-6 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
        <div
          className="h-full bg-gradient-brand transition-all"
          style={{ width: `${(doneCount / steps.length) * 100}%` }}
        />
      </div>

      <ol className="space-y-4">
        {steps.map((step) => (
          <li key={step.n}>
            <GlassCard gradTop={!step.done}>
              <div className="flex items-start gap-4">
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-[13px] ${
                  step.done
                    ? 'bg-[var(--color-success)] text-[var(--color-bg)]'
                    : 'bg-[rgba(58,130,255,0.15)] text-[var(--color-accent-blue)]'
                }`}>
                  {step.done ? '✓' : step.n}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="mb-3 text-[15px] font-semibold">{step.title}</h3>
                  {step.body}
                </div>
              </div>
            </GlassCard>
          </li>
        ))}
      </ol>

      <p className="mt-8 text-center font-mono text-[11px] text-[var(--color-body)]">
        Stuck? Read the{' '}
        <a href="https://github.com/Gradata/gradata" className="text-[var(--color-accent-blue)] underline">SDK docs</a>{' '}
        or email{' '}
        <a href="mailto:support@gradata.ai" className="text-[var(--color-accent-blue)] underline">support@gradata.ai</a>.
      </p>
    </>
  )
}

function CodeBlock({ code, onCopy, copied, language }: {
  code: string
  onCopy: () => void
  copied: boolean
  language?: string
}) {
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-[0.5rem] border border-[var(--color-border)] bg-black/40 p-4 font-mono text-[12px] leading-relaxed">
        {code}
      </pre>
      <button
        type="button"
        onClick={onCopy}
        className="absolute right-3 top-3 rounded-[0.25rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.8)] px-2.5 py-1 font-mono text-[10px] text-[var(--color-body)] backdrop-blur-md transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
      >
        {copied ? 'copied' : 'copy'}
      </button>
      {language && (
        <span className="absolute left-3 top-3 font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]/40">
          {language}
        </span>
      )}
    </div>
  )
}

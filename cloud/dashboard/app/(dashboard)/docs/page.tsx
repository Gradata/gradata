'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'

/**
 * In-dashboard docs page — common SDK patterns, copy-paste-ready.
 * Lives behind auth so we can later show personalized snippets
 * (e.g. inject the user's API key into the example).
 */

interface Snippet {
  id: string
  title: string
  language: 'bash' | 'python' | 'typescript'
  code: string
  notes?: string
}

const SNIPPETS: Array<{ section: string; items: Snippet[] }> = [
  {
    section: 'Install',
    items: [
      {
        id: 'install',
        title: 'Install the SDK',
        language: 'bash',
        code: 'pip install gradata',
      },
      {
        id: 'verify',
        title: 'Verify install',
        language: 'bash',
        code: `python -c "import gradata; print(gradata.__version__)"`,
      },
    ],
  },
  {
    section: 'Initialize a brain',
    items: [
      {
        id: 'init-local',
        title: 'Local-only brain (no cloud sync)',
        language: 'python',
        code: `import gradata

brain = gradata.Brain.init(
    name="my-brain",
    domain="engineering",  # any string — used to scope rules
)`,
        notes: 'Local mode — corrections + lessons stay on disk in `~/.gradata/<name>/`. No network.',
      },
      {
        id: 'init-cloud',
        title: 'Cloud-synced brain',
        language: 'python',
        code: `import gradata

brain = gradata.Brain.init(
    name="my-brain",
    domain="engineering",
    api_key="gd_YOUR_KEY_HERE",  # generate at app.gradata.ai/api-keys
)`,
        notes: 'Synthesized principles + counters reach api.gradata.ai. Raw correction text NEVER leaves your machine.',
      },
    ],
  },
  {
    section: 'Run a session',
    items: [
      {
        id: 'session',
        title: 'Wrap your work in a session',
        language: 'python',
        code: `with brain.session() as s:
    response = s.ask("Draft a response to this RFP question")
    # ... your code uses response ...

# Corrections you log in this session sync at end_session()`,
      },
      {
        id: 'correct',
        title: 'Log a correction',
        language: 'python',
        code: `brain.correct(
    draft="We are pleased to inform you of our quarterly results.",
    final="Our Q3 numbers are in — here's what changed.",
    category="Tone & Register",  # optional; SDK auto-classifies
)`,
        notes: 'Severity is computed automatically from edit-distance. SDK extracts the behavioral instruction.',
      },
    ],
  },
  {
    section: 'Inject rules into a prompt',
    items: [
      {
        id: 'inject',
        title: 'Get the active rules for a prompt',
        language: 'python',
        code: `prompt = "Draft a follow-up to last week's investor email."

rules = brain.rules_for(prompt, max=10)
# rules is a list of strings — graduated principles
# Inject them into your system prompt:
system = "You are an assistant.\\n\\nFollow these:\\n" + "\\n".join(f"- {r}" for r in rules)`,
        notes: 'max=10 caps the injection budget. SDK picks the most relevant + highest-confidence rules.',
      },
    ],
  },
  {
    section: 'Inspect what the brain learned',
    items: [
      {
        id: 'inspect',
        title: 'List graduated rules',
        language: 'python',
        code: `for lesson in brain.lessons(state="RULE"):
    print(f"{lesson.confidence:.2f}  {lesson.description}")
`,
      },
      {
        id: 'meta',
        title: 'Find meta-rules (universal principles)',
        language: 'python',
        code: `for meta in brain.meta_rules():
    print(meta.title)
    print(f"  derived from {len(meta.source_lessons)} rules")
`,
      },
    ],
  },
  {
    section: 'CLI',
    items: [
      {
        id: 'cli-init',
        title: 'Initialize a brain from the command line',
        language: 'bash',
        code: `gradata init my-brain --domain engineering`,
        notes: 'Same as Brain.init() but driven from the shell. Use GRADATA_API_KEY env var to enable cloud sync.',
      },
      {
        id: 'cli-stats',
        title: 'See what the brain has learned',
        language: 'bash',
        code: `gradata stats my-brain
gradata search my-brain "tone"`,
        notes: 'stats prints lesson + correction counts grouped by state. search returns matching lessons by query.',
      },
      {
        id: 'cli-context',
        title: 'Print the active rules for a prompt',
        language: 'bash',
        code: `gradata context my-brain "Draft a follow-up email to investors"`,
        notes: 'Same as brain.rules_for() but pipes to stdout — handy for scripts and other LLM tools.',
      },
    ],
  },
  {
    section: 'MCP server',
    items: [
      {
        id: 'mcp-claude',
        title: 'Run as an MCP server (Claude Desktop, Cursor, etc.)',
        language: 'bash',
        code: `python -m gradata.mcp_server --brain my-brain`,
        notes: "Serves brain.rules_for(), brain.search(), and brain.lessons() over MCP. Add to your MCP host's config.",
      },
      {
        id: 'mcp-config',
        title: 'Sample claude_desktop_config.json',
        language: 'typescript',
        code: `{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain", "my-brain"],
      "env": { "GRADATA_API_KEY": "gd_YOUR_KEY" }
    }
  }
}`,
        notes: 'Drop this into ~/Library/Application Support/Claude/claude_desktop_config.json (mac) or %APPDATA%/Claude/ (win).',
      },
    ],
  },
  {
    section: 'TypeScript / JavaScript',
    items: [
      {
        id: 'ts-install',
        title: 'Install the JS SDK',
        language: 'bash',
        code: 'npm install @gradata/sdk',
        notes: 'JS SDK is a thin wrapper around the cloud API. For full graduation engine, use the Python SDK.',
      },
      {
        id: 'ts-correct',
        title: 'Log a correction from a Node app',
        language: 'typescript',
        code: `import { Brain } from '@gradata/sdk'

const brain = new Brain({ apiKey: process.env.GRADATA_API_KEY! })

await brain.correct({
  draft: "We are pleased to inform you...",
  final: "Hey, quick update —",
  category: 'Tone & Register',
})`,
      },
    ],
  },
]

export default function DocsPage() {
  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Docs</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Copy-paste-ready snippets for the most common Gradata SDK patterns
        </p>
      </header>

      <div className="space-y-8">
        {SNIPPETS.map((section) => (
          <section key={section.section}>
            <h2 className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--color-accent-blue)]">
              {section.section}
            </h2>
            <div className="space-y-4">
              {section.items.map((item) => (
                <SnippetCard key={item.id} snippet={item} />
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-12 text-center">
        <p className="font-mono text-[11px] text-[var(--color-body)]">
          Full reference at{' '}
          <a
            href="https://github.com/Gradata/gradata"
            className="text-[var(--color-accent-blue)] underline-offset-4 hover:underline"
          >
            github.com/Gradata/gradata
          </a>
        </p>
      </div>
    </>
  )
}

function SnippetCard({ snippet }: { snippet: Snippet }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(snippet.code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <GlassCard gradTop>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="text-[14px] font-semibold">{snippet.title}</h3>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">
          {snippet.language}
        </span>
      </div>
      <div className="relative">
        <pre className="overflow-x-auto rounded-[0.5rem] border border-[var(--color-border)] bg-black/40 p-4 font-mono text-[12px] leading-relaxed">
          {snippet.code}
        </pre>
        <button
          type="button"
          onClick={copy}
          className="absolute right-3 top-3 rounded-[0.25rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.8)] px-2.5 py-1 font-mono text-[10px] text-[var(--color-body)] backdrop-blur-md transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
        >
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      {snippet.notes && (
        <p className="mt-3 text-[11px] text-[var(--color-body)]">{snippet.notes}</p>
      )}
    </GlassCard>
  )
}

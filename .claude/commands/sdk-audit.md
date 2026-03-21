## SDK Boundary Audit

Scan core architecture files for Sprites-specific contamination. Report only — never auto-edit or delete.

### Files to Scan
1. `CLAUDE.md` (project root)
2. `agents/registry.md`
3. All hook files in `.claude/hooks/` (glob `*.js`)
4. All RAG embed scripts in `brain/scripts/` (glob `*.py`)

### What Counts as Sprites-Specific
Flag any content that references:
- Real prospect names (people or companies from brain/prospects/)
- Company names from the Sprites pipeline
- Personal outreach patterns tied to Sprites.ai sales
- Direct references to "Sprites.ai" or "Sprites" as a product/company
- Domain-specific sales logic that would not apply to a generic user of [NAME] (e.g., specific CRM field mappings, Instantly campaign IDs, persona names like "agency-owner" that are Sprites ICP-specific)

### Output Format
For each file scanned, output a block like:

```
### [filename]
Status: CONTAMINATED | REVIEW | CLEAN

Findings:
- Line N: [quoted content] — [reason it's flagged]
- Line N: [quoted content] — [reason it's flagged]
```

Status definitions:
- **CONTAMINATED** — Clearly Sprites-specific content present that must be removed or abstracted before SDK extraction
- **REVIEW** — Ambiguous content that may need manual evaluation (e.g., a path that could be generic or could be Sprites-specific)
- **CLEAN** — No Sprites-specific content detected

### Rules
- Scan every file listed above. Do not skip any.
- Do NOT edit, delete, or modify any file. This is a read-only audit.
- All cleanup decisions are made manually by the user after reviewing the report.
- At the end, print a summary table: filename | status | finding count
- Reference `brain/vault/sdk-north-star.md` for strategic context on the boundary between Sprites Work and [NAME].

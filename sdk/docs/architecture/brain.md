# Layer 2: Trained Brain

Layer 2 is the trained data itself, stored in a SQLite database and markdown files within the brain directory.

## What's in a Brain

```
my-brain/
├── system.db               # All structured data
├── brain.manifest.json     # Quality proof
├── .embed-manifest.json    # Embedding hash tracker
├── knowledge/              # Domain knowledge (markdown)
├── prospects/              # Contact notes (if sales)
├── sessions/               # Session summaries
└── taxonomy.json           # Custom tag definitions
```

## system.db Schema

The SQLite database contains all structured brain state:

### events

The core table. Every brain operation emits an event.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `ts` | TEXT | ISO 8601 timestamp |
| `session` | INTEGER | Session number |
| `type` | TEXT | Event type (CORRECTION, OUTPUT, RULE_APPLICATION, etc.) |
| `source` | TEXT | What emitted the event |
| `data_json` | TEXT | Event payload as JSON |
| `tags_json` | TEXT | Searchable tags as JSON array |

### brain_fts

FTS5 virtual table for full-text search over brain knowledge files.

### brain_embeddings

Vector embeddings for semantic search (requires `sentence-transformers` or `google-genai`).

### facts

Structured facts extracted from prospect files and knowledge documents.

## brain.manifest.json

The manifest is a machine-readable quality proof, regenerated from event data each session:

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "brain_version": "0.1.0",
    "sessions_trained": 44,
    "maturity_phase": "INFANT",
    "domain": "Sales",
    "name": "Oliver's Sales Brain"
  },
  "quality": {
    "correction_rate": 0.23,
    "lessons_active": 13,
    "lessons_graduated": 66,
    "events_total": 1088
  },
  "rag": {
    "files_indexed": 165,
    "embedding_chunks": 1088,
    "search_modes": ["fts5"]
  }
}
```

The manifest is the brain's resume. It proves how much training has happened and what quality level was achieved, without exposing raw data.

## Maturity Phases

Brains progress through maturity phases based on training depth:

| Phase | Sessions | Characteristics |
|-------|----------|----------------|
| **NEWBORN** | 0-5 | Initial setup, few corrections |
| **INFANT** | 6-50 | Building patterns, high correction rate |
| **ADOLESCENT** | 51-200 | Patterns graduating, correction rate declining |
| **MATURE** | 201+ | Stable rules, low correction rate, self-cleaning |

## Event Flow

```
log_output() → OUTPUT event
correct()    → CORRECTION event → Diff → Classify → Extract Patterns
manifest()   → Reads all events → Computes quality metrics → Writes JSON
health()     → Reads events + DB → Returns health report
```

All derived state (metrics, manifests, reports) is computed on demand from the event log.

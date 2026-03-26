# Gradata Cloud

Gradata Cloud is the hosted intelligence layer for AIOS Brain. It runs the adaptation engine, quality scoring, and cross-brain learning that makes brains compound faster than local-only mode.

## Local vs Cloud

| Capability | Local (free) | Cloud |
|-----------|-------------|-------|
| Store corrections and events | yes | yes |
| FTS5 keyword search | yes | yes |
| Base agentic patterns | yes | yes |
| MCP server integration | yes | yes |
| Correction analysis | basic | advanced |
| Behavioral rule promotion | local only | server-side + cross-brain learning |
| Quality scoring + Report Card | basic | 5-dimension validator |
| Compound growth metrics | manual | automatic + dashboard |
| Cross-brain learning | no | yes |
| Marketplace listing | no | yes |
| Brain backup + versioning | manual | automatic |
| Team sharing | no | yes |

## How It Works

```
Local Brain (SQLite)
    ↓ sync
Gradata Cloud
    ↓ adaptation engine
    ↓ cross-brain learning
    ↓ quality scoring
    ↓ marketplace readiness
    ↓ sync back
Local Brain (enriched rules)
```

When connected, your brain syncs events to the cloud. The cloud runs the full adaptation pipeline with access to patterns identified across all brains on the platform. Proven rules sync back to your local brain automatically.

## The Cross-Brain Advantage

Local mode identifies patterns from your corrections alone. Cloud mode sees patterns across thousands of brains:

- A behavioral rule that proved itself in 847 sales brains starts with higher trust in yours
- Patterns that consistently fail across the platform get flagged before they waste your time
- Domain-specific insights compound across all users in that domain

This cross-brain signal accelerates your brain's improvement. Patterns that already proved themselves elsewhere don't need to start from scratch in your brain.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Gradata Cloud (proprietary)              │
│  Adaptation engine · Quality validator      │
│  Cross-brain learning · Marketplace         │
├─────────────────────────────────────────────┤
│  Cloud Sync (urllib, zero deps)             │
│  brain.connect_cloud() · auto-sync          │
├─────────────────────────────────────────────┤
│  AIOS Brain SDK (open source)               │
│  Patterns · Events · Search · MCP           │
└─────────────────────────────────────────────┘
```

The SDK is fully functional without the cloud. The cloud adds acceleration, not dependency.

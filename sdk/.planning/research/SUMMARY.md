# Research Summary: AIOS Brain SDK Production Readiness

**Domain:** Python SDK for AI brain management (knowledge compounding, event-sourced learning)
**Researched:** 2026-03-24
**Overall confidence:** HIGH (based on direct comparison with Stripe, OpenAI, google-cloud-python source code)

## Executive Summary

The aios-brain SDK has unusually strong foundations for a v0.1.0: event-sourced data model, 537 tests, MCP server, zero required deps, domain-agnostic config, schema migrations, and a brain validator. These are things most SDKs bolt on later. What's missing is the packaging and developer-experience layer that separates "works for us" from "works for strangers."

The critical gaps are: (1) no custom exception hierarchy -- users catch bare `ValueError`/`ImportError` with no SDK-specific handling, (2) no `py.typed` marker -- type checkers ignore the package, (3) no structured logging -- debugging is print-and-pray, (4) no deprecation machinery -- any API change is a breaking change with no migration path. These four gaps are each individually small (2-8 hours) but collectively they're the difference between "alpha" and "beta."

The non-critical-but-expected gaps are: API reference docs (mkdocs-material + mkdocstrings), a CHANGELOG, examples directory, and property-based tests for the core data model. These take 1-2 days total and are table stakes for any PyPI package that expects external adoption.

The SDK should NOT invest time in: OpenTelemetry integration (premature for the user base), SBOM generation (no supply chain risk with zero deps), or mutation testing (537 tests is already well above the bar).

## Key Findings

**Stack:** Hatchling build, pure Python, zero deps -- this is correct and should not change.
**Architecture:** Event-sourced with SQLite is a strong foundation; needs exception boundary layer on top.
**Critical pitfall:** Users will catch `ValueError` from 15 different call sites with no way to distinguish SDK errors from their own code's errors.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Exception Foundation** (4 hours) - Custom exception hierarchy, error codes
   - Addresses: Error handling, debuggability
   - Avoids: Users unable to catch/handle SDK errors distinctly

2. **Packaging Polish** (3 hours) - py.typed, CHANGELOG, LICENSE file, examples/
   - Addresses: PyPI readiness, type checker support
   - Avoids: "This doesn't feel like a real package" first impression

3. **Observability Layer** (6 hours) - Structured logging, debug mode, event hooks
   - Addresses: "Why did my brain do that?" debugging
   - Avoids: Users filing issues that are actually their own misconfiguration

4. **Deprecation System** (3 hours) - warnings.deprecated decorator, version policy
   - Addresses: Backward compatibility for post-v1.0 changes
   - Avoids: Breaking changes with no migration path

5. **Documentation** (8 hours) - mkdocs-material site, API reference, examples
   - Addresses: External developer onboarding
   - Avoids: "I can't figure out how to use this" abandonment

**Phase ordering rationale:**
- Exceptions first because every other layer depends on them (logging wraps exceptions, docs reference them, deprecation warnings are a form of error signaling)
- Packaging before docs because you can't generate API docs from a package type checkers can't read
- Documentation last because it documents the stable API surface, not the moving target

**Research flags for phases:**
- Phase 1 (Exceptions): Straightforward, patterns well-established. No further research needed.
- Phase 3 (Observability): May need deeper research on what brain-specific events to expose (not just generic logging).
- Phase 5 (Docs): mkdocs-material + mkdocstrings is the clear winner, but hosting decision (GitHub Pages vs Read the Docs) deferred.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against Stripe, OpenAI, PydanticAI source |
| Features | HIGH | Direct comparison with 4 production SDKs |
| Architecture | HIGH | Event-sourced model is well-suited; exception layer is gap |
| Pitfalls | MEDIUM | Some pitfalls (e.g., SQLite concurrency at scale) are theoretical |

## Gaps to Address

- Hosting strategy for docs (GitHub Pages vs Read the Docs) -- deferred to docs phase
- Whether `chromadb` optional dep should be replaced with `sqlite-vec` per S42 research findings
- Entry points for plugin/extension system (not needed for v1.0 but affects exception hierarchy design)

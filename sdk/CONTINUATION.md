# SDK Continuation — S40 → S41

## Current State
21 modules, pip-installable, 9 tests passing. Shim architecture live (brain/scripts/ imports from SDK). Import binding fixed (_p. pattern). Validator Grade A. Self-improvement pipeline ported.

## Next Steps
1. Test on Oliver's second machine — full cycle: init → embed → search → emit → manifest → validate → export
2. Fix any failures from second-machine test
3. More tests: semantic search, context compilation, install flow, error paths
4. README rewrite for external developers
5. CONTRIBUTING.md + docstring audit

## Known Issues
- Some SDK modules may still have `from aios_brain._paths import X` (value binding) instead of `import aios_brain._paths as _p` (module reference) — check _context_packet.py, _export_brain.py
- `_doctor.py` shows 9/10 (1 check may depend on Oliver's env)
- Self-improvement pipeline is pure logic — needs integration into a session lifecycle (wrap_up calls it, but SDK standalone doesn't have a wrap_up equivalent yet)

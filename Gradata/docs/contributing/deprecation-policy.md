# Deprecation Policy

## Scope
Applies to every public symbol, import path, CLI command, and config key in
`gradata` that is marked for removal via `DeprecationWarning`, a
`.. deprecated::` docstring tag, or a CHANGELOG entry tagged `DEPRECATED`.

## Lifecycle
1. **Mark.** The deprecating release MUST:
   - Emit `DeprecationWarning` at first use (module-level via `__getattr__`
     where possible, otherwise at function entry).
   - Add `.. deprecated:: X.Y.Z` to the symbol's docstring.
   - Add a `DEPRECATED` bullet to CHANGELOG naming the replacement.
2. **Carry.** The symbol SHALL remain callable through **two additional minor
   versions** after the deprecating release, then be removed.
   - Deprecated in 0.6.x → removed in 0.8.0 (earliest).
   - No removal inside a patch bump.
3. **Remove.** The removing release MUST:
   - Add a `BREAKING` bullet to CHANGELOG with the old path → new path.
   - Delete the shim, its tests, and any docs that reference it.

## Exceptions
- **Security fixes** may remove a deprecated path earlier. CHANGELOG must
  state "removed early for security" with a CVE or internal ticket.
- **Pre-0.7.0 relaxation.** Before 0.7.0 ships, early removal is permitted
  if the CHANGELOG `BREAKING` section names the symbol explicitly. Once
  0.7.0 ships, the two-minor-version rule binds.

## Non-deprecation refactors
Moving a non-deprecated module (rename, relocation) counts as a breaking
change and follows the same two-minor-version carry rule via a forwarding
shim. The move itself triggers the deprecation clock.

## Why two versions
One version is the window users realistically notice the warning in their
test suite. The second is the window they schedule the migration. Removing
after one minor version breaks users who followed the warning in good faith.

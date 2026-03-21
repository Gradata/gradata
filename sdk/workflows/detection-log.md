# Workflow Detection Log

> Append-only during sessions. Compacted every 10 sessions.
> Format: session date | task signature | steps observed | match count | status

---

## Active Signatures

<!-- Populated automatically at session wrap-up when major tasks complete. -->
<!-- Format: -->
<!-- | Date | Signature Hash | Task Type | Tools | Steps | Matches | Status | -->

| Date | Signature | Task Type | Tools | Steps | Matches | Status |
|------|-----------|-----------|-------|-------|---------|--------|

## Declined Signatures

<!-- Signatures the user declined. Cooldown = 10 sessions from decline date. -->

| Date Declined | Signature | Cooldown Expires | Re-suggested? |
|---------------|-----------|-----------------|---------------|

## Saved Workflows

<!-- Signatures that became saved workflows. Detection stops for these. -->

| Date Saved | Signature | Workflow File | Sessions Observed |
|------------|-----------|--------------|-------------------|

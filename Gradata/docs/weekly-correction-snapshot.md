# Weekly Correction Snapshot

`scripts/weekly_correction_snapshot.py` builds a deterministic JSON summary from newline-delimited JSON (NDJSON) events. This is intended for weekly correction-outcome trend reporting.

## Usage

From file:

```bash
python scripts/weekly_correction_snapshot.py --input /path/to/events.jsonl
```

From stdin:

```bash
cat /path/to/events.jsonl | python scripts/weekly_correction_snapshot.py
```

## Output schema

The script always emits one compact JSON object with stable key ordering:

- `total_corrections` (int): count of correction events (`event=correction.created` or `kind=correction`)
- `accepted_graduations` (int): count of accepted graduation outcomes
- `rejection_count` (int): count of rejected graduation outcomes
- `acceptance_rate` (float): `accepted_graduations / (accepted_graduations + rejection_count)`, or `0.0` if denominator is zero
- `top_rule_categories` (list): up to 5 entries sorted by descending count, then category name
- `skipped_rows` (int): malformed or non-object rows ignored during parsing

`top_rule_categories` entries use:

```json
{"category":"tone","count":12}
```

Category normalization is lowercase + trimmed whitespace. Empty/missing categories normalize to `"unknown"`.

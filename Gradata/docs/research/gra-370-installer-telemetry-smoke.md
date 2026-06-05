# GRA-370 installer telemetry + hook registration smoke

Date: 2026-06-04
Issue: GRA-370

## Scope

Smoke the current SDK installer/hook registration path for the host targets relevant to the original GRA-370 request:

- Codex hook config
- Hermes hook config
- Cursor install matrix row
- Shared host adapter contracts used by Claude Code/Codex/Hermes/OpenCode

The repository has since moved away from the older npm `setup/install.js` path. Current main-branch docs point developers at the Python CLI surface:

```bash
gradata install --agent <host>
```

Cursor is MCP-only in the current install matrix and is intentionally represented by a skipped matrix row rather than a fake hook install.

## Verification command

Run from `Gradata/`:

```bash
env -u BRAIN_DIR -u GRADATA_BRAIN /home/olive/.local/bin/uv run pytest \
  tests/test_install_smoke_matrix.py \
  tests/test_cli_install_agent.py \
  tests/test_hook_adapters.py \
  -q
```

## Result

```text
....s......s........................                                     [100%]
34 passed, 2 skipped in 2.88s
```

## Failure case captured

The first run inherited the live agent environment's `BRAIN_DIR`/`GRADATA_BRAIN`, so installer tests wrote `/home/olive/.gradata/brain` into generated configs instead of the test-specific `--brain <tmp>` path. That produced eight assertion failures in:

- `tests/test_install_smoke_matrix.py`
- `tests/test_cli_install_agent.py`

Rerunning with both variables unset produced the passing result above. This is an environment-contamination pitfall, not a product regression.

## Host observations

| Host | Current smoke evidence |
| --- | --- |
| Codex | `tests/test_install_smoke_matrix.py`, `tests/test_cli_install_agent.py`, and `tests/test_hook_adapters.py` verify `.codex/config.toml` hook registration. |
| Hermes | `tests/test_install_smoke_matrix.py` and `tests/test_cli_install_agent.py` verify `.hermes/config.yaml` native hook names. |
| Cursor | Current matrix marks Cursor MCP-only and skips hook/slash-command assertions instead of pretending Cursor has stdin lifecycle hooks. |

## Follow-up

No code regression was found in the isolated test run. Keep future smoke runs isolated from the agent's live `BRAIN_DIR`/`GRADATA_BRAIN` environment when asserting explicit `--brain` behavior.

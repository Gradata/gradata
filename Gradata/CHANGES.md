## P0-5: rule_graph.json Atomic Writes

- Added `src/gradata/_atomic.py` with `atomic_write_text()`, which writes through a sibling temp file, fsyncs the file, atomically replaces the target, and fsyncs the directory on POSIX.
- Updated `src/gradata/rules/rule_graph.py` so `RuleGraph.save()` no longer writes `rule_graph.json` directly.
- Added `tests/test_rule_graph_atomic.py::test_rule_graph_save_preserves_prior_state_when_replace_fails`.
- Verified with: `python3 -c "from tests.test_rule_graph_atomic import test_rule_graph_save_preserves_prior_state_when_replace_fails; test_rule_graph_save_preserves_prior_state_when_replace_fails()"`

## P0-4: BRAIN_DIR-Unresolved Hard Fail

- Added `GradataError` and `BrainNotConfiguredError` to `src/gradata/exceptions.py`.
- Updated `src/gradata/hooks/implicit_feedback.py` to raise `BrainNotConfiguredError` when feedback signals are detected but no brain directory can be resolved.
- Updated `src/gradata/hooks/_base.py` so the hook runner does not suppress `BrainNotConfiguredError`.
- Updated `src/gradata/_doctor.py` so missing `BRAIN_DIR` is reported as a clear `brain_dir` failure instead of an optional skip.
- Updated the existing implicit feedback no-brain test expectation and added `tests/test_brain_dir_required.py`.
- Verified with: `python3 -c "from tests.test_brain_dir_required import test_implicit_feedback_raises_without_brain_dir, test_doctor_reports_missing_brain_dir, test_hook_runner_does_not_suppress_brain_not_configured; test_implicit_feedback_raises_without_brain_dir(); test_doctor_reports_missing_brain_dir(); test_hook_runner_does_not_suppress_brain_not_configured()"`

## P0-7: Package Import Integrity Check

- Added `tests/test_import_integrity.py` with a subprocess smoke test for `import gradata`, `Brain`, `Lesson`, and `LessonState`.
- Added a direct `Brain.init()` smoke test against a temporary brain directory.
- Verified with: `python3 -c "from tests.test_import_integrity import test_public_imports_work_in_subprocess, test_brain_init_smoke_in_tmp_path; test_public_imports_work_in_subprocess(); test_brain_init_smoke_in_tmp_path()"`

## P0-6: Thread-Safety Service Lock

- Added `BrainLockedError` to `src/gradata/exceptions.py`.
- Added `src/gradata/_brain_lock.py` with `acquire_brain_lock(brain_dir)`, using non-blocking `fcntl.flock` on POSIX and `msvcrt.locking` on Windows, plus an in-process duplicate-lock guard.
- Wired `src/gradata/daemon.py` to acquire the lock when `GradataDaemon.start()` begins and release it during cleanup.
- Wired `src/gradata/mcp_server.py` to acquire the lock for the duration of `run_server()` after the brain is initialized.
- Exported `GradataError`, `BrainNotConfiguredError`, and `BrainLockedError` from `src/gradata/__init__.py`.
- Added `tests/test_brain_lock.py::test_second_mock_daemon_raises_brain_locked`.
- Verified with: `python3 -c "from tests.test_brain_lock import test_second_mock_daemon_raises_brain_locked; test_second_mock_daemon_raises_brain_locked()"`

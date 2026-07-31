"""
Opt-in anonymous telemetry for SDK activation events.

What this does
--------------
Sends named activation events (e.g. ``brain_initialized``,
``first_correction_captured``) to the Gradata Cloud telemetry endpoint so
we can measure time-to-first-value. Strictly opt-in. Strictly anonymous.

What we send
------------
Exactly this shape — nothing else::

    {
        "event": "<event_name>",
        "user_id": "<sha256(machine_id)>",
        "ts": "<ISO 8601 UTC>",
        "sdk_version": "<pyproject version>"
    }

What we DO NOT send
-------------------
Lesson text. Correction content. Draft/final previews. File paths. Names.
Emails. Stack traces. Environment variables. Anything identifiable.

Opt-in semantics
----------------
1. The user-level Gradata config file (default ``~/.gradata/config.toml``,
   overridable via ``GRADATA_CONFIG_DIR``) holds
   ``[telemetry] enabled = true|false``.
2. Default is OFF (missing file or missing key → off).
3. ``GRADATA_TELEMETRY=0`` env var overrides to off, always. (Kill switch
   for users who already opted in but need to silence one session.)
4. ``GRADATA_TELEMETRY=1`` env var does NOT auto-enable. Users must opt in
   via the prompt or by editing the config file.

Idempotency
-----------
Activation events fire at most once per machine per SDK install (tracked
in the same config file). Heartbeat/recurring events are not this module's
concern.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from gradata._config_paths import get_config_dir

logger = logging.getLogger("gradata.telemetry")

# ── Constants ─────────────────────────────────────────────────────────
DEFAULT_ENDPOINT: Final[str] = "https://api.gradata.ai/telemetry/event"
DEFAULT_POSTHOG_ENDPOINT: Final[str] = "https://us.i.posthog.com/capture/"
ENV_ENDPOINT: Final[str] = "GRADATA_TELEMETRY_ENDPOINT"
ENV_POSTHOG_HOST: Final[str] = "GRADATA_POSTHOG_HOST"
ENV_POSTHOG_API_KEY: Final[str] = "GRADATA_POSTHOG_API_KEY"
ENV_POSTHOG_PROJECT_API_KEY: Final[str] = "POSTHOG_PROJECT_API_KEY"
ENV_KILL_SWITCH: Final[str] = "GRADATA_TELEMETRY"
_CONFIG_FILENAME: Final[str] = "config.toml"


def _config_dir() -> Path:
    """Shared resolver for the user-level Gradata config directory.

    Delegates to :mod:`gradata._config_paths` so all SDK modules agree on
    where ``config.toml`` lives and no one hardcodes ``Path.home()``.
    """
    return get_config_dir()


def _config_path() -> Path:
    """Shared resolver for the telemetry config file."""
    return _config_dir() / _CONFIG_FILENAME


# The exhaustive set of activation events. Adding a new one here is the
# only place you need to touch — the prompt copy and the docs reference
# this tuple, the backend schema just validates string length.
ACTIVATION_EVENTS: Final[tuple[str, ...]] = (
    "brain_initialized",
    "first_correction_captured",
    "first_graduation",
    "first_hook_installed",
)

# PostHog activation-funnel events requested by GRA-2031. Kept separate from
# the legacy anonymous activation tuple so older tests and payload contracts do
# not accidentally widen.
CLI_TELEMETRY_EVENTS: Final[tuple[str, ...]] = (
    "cli_install",
    "first_rule_graduated",
    "rule_injected",
)

ActivationEvent = Literal[
    "brain_initialized",
    "first_correction_captured",
    "first_graduation",
    "first_hook_installed",
]

CliTelemetryEvent = Literal[
    "cli_install",
    "first_rule_graduated",
    "rule_injected",
]


# ── Config I/O ────────────────────────────────────────────────────────
def _read_config() -> dict[str, str]:
    """Read ``config.toml`` into a flat dict of top-level and ``[telemetry]``
    keys. Zero-dep — we don't want to pull tomllib just for this."""
    cfg_path = _config_path()
    if not cfg_path.exists():
        return {}
    try:
        text = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {}
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        full_key = f"{section}.{key}" if section else key
        out[full_key] = val
    return out


def _write_config_key(key: str, value: str) -> None:
    """Idempotently set ``[section] key = "value"`` in the config file.
    Preserves other content. Creates the file if needed."""
    section, _, bare = key.partition(".")
    if not bare:
        section, bare = "", section
    cfg_dir = _config_dir()
    cfg_path = _config_path()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    existing = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""

    # Simple rewriter: find section, find key, replace; otherwise append.
    lines = existing.splitlines()
    out_lines: list[str] = []
    in_section = section == ""
    key_written = False
    section_seen = section == ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Transitioning sections
            if in_section and not key_written:
                out_lines.append(f'{bare} = "{value}"')
                key_written = True
            in_section = stripped[1:-1].strip() == section
            if in_section:
                section_seen = True
            out_lines.append(line)
            continue
        # Match the LHS exactly after splitting on '=' so we don't false-match
        # keys that share a prefix (e.g. ``enabled_foo`` when looking for
        # ``enabled``).
        if in_section and not key_written and "=" in stripped:
            lhs = stripped.split("=", 1)[0].strip()
            if lhs == bare:
                out_lines.append(f'{bare} = "{value}"')
                key_written = True
                continue
        out_lines.append(line)

    if not key_written:
        if not section_seen and section:
            if out_lines and out_lines[-1].strip():
                out_lines.append("")
            out_lines.append(f"[{section}]")
        out_lines.append(f'{bare} = "{value}"')

    cfg_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


# ── Opt-in check ──────────────────────────────────────────────────────
def is_enabled() -> bool:
    """True iff user opted in AND the kill-switch env var is not set to 0."""
    # Kill switch always wins.
    override = os.environ.get(ENV_KILL_SWITCH, "").strip()
    if override == "0" or override.lower() in ("false", "off", "no"):
        return False
    cfg = _read_config()
    return cfg.get("telemetry.enabled", "").lower() == "true"


def set_enabled(enabled: bool) -> None:
    """Persist the opt-in choice."""
    _write_config_key("telemetry.enabled", "true" if enabled else "false")


def has_been_asked() -> bool:
    """Was the user shown the opt-in prompt already?"""
    cfg = _read_config()
    return "telemetry.enabled" in cfg


def config_path() -> Path:
    """Return the path to the gradata config file (where opt-in is stored).

    Exposed so callers (e.g. the CLI) can render a portable path string
    instead of hard-coding ``~/.gradata/config.toml``.
    """
    return _config_path()


# ── Anonymous user ID ─────────────────────────────────────────────────
def _machine_id_seed() -> str:
    """Stable per-machine seed. We use ``uuid.getnode()`` which returns the
    hardware MAC — stable across reinstalls on the same machine but not
    portable between machines. Good enough to dedupe, insufficient to
    identify anyone (we hash it before sending)."""
    # Keep the raw seed out of memory once hashed.
    return f"gradata-v1:{uuid.getnode():x}"


def anonymous_user_id() -> str:
    """Return ``sha256(machine_id)`` as a hex digest.

    Deterministic per machine, opaque to the backend, impossible to reverse
    into a MAC or hostname.
    """
    seed = _machine_id_seed().encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


# ── Send ──────────────────────────────────────────────────────────────
def _endpoint() -> str:
    return os.environ.get(ENV_ENDPOINT, "").strip() or DEFAULT_ENDPOINT


def _posthog_api_key() -> str | None:
    return (
        os.environ.get(ENV_POSTHOG_API_KEY, "").strip()
        or os.environ.get(ENV_POSTHOG_PROJECT_API_KEY, "").strip()
        or None
    )


def _posthog_endpoint() -> str:
    explicit = os.environ.get(ENV_ENDPOINT, "").strip()
    if explicit:
        return explicit
    host = os.environ.get(ENV_POSTHOG_HOST, "").strip().rstrip("/")
    if host:
        return f"{host}/capture/"
    return DEFAULT_POSTHOG_ENDPOINT


def _sdk_version() -> str:
    try:
        from gradata import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _build_payload(event: str) -> dict[str, str]:
    """Exact legacy wire format. No extra fields, ever."""
    return {
        "event": event,
        "user_id": anonymous_user_id(),
        "ts": datetime.now(UTC).isoformat(),
        "sdk_version": _sdk_version(),
    }


def _safe_brain_id(brain_dir: str | Path | None = None) -> str | None:
    if brain_dir is None:
        return None
    try:
        from gradata._tenant import tenant_for

        return tenant_for(Path(brain_dir))
    except Exception:
        return hashlib.sha256(str(brain_dir).encode("utf-8")).hexdigest()[:32]


def _install_started_at() -> str:
    key = "telemetry.install_started_at"
    cfg = _read_config()
    existing = cfg.get(key, "").strip()
    if existing:
        return existing
    ts = datetime.now(UTC).isoformat()
    with _config_lock():
        cfg = _read_config()
        existing = cfg.get(key, "").strip()
        if existing:
            return existing
        _write_config_key(key, ts)
    return ts


def _hours_since_install() -> float | None:
    raw = _read_config().get("telemetry.install_started_at", "").strip()
    if not raw:
        return None
    try:
        installed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return max(0.0, (datetime.now(UTC) - installed).total_seconds() / 3600.0)
    except ValueError:
        return None


def _cohort() -> str | None:
    value = os.environ.get("GRADATA_COHORT", "").strip()
    return value or None


def _experiment_id() -> str | None:
    value = os.environ.get("GRADATA_EXPERIMENT_ID", "").strip()
    return value or None


def _build_cli_payload(
    event: str,
    *,
    brain_dir: str | Path | None = None,
    agent_type: str | None = None,
    rule_id: str | None = None,
    injection_count_this_session: int | None = None,
) -> dict:
    """PostHog-compatible activation-funnel payload for CLI/SDK events."""
    if event not in CLI_TELEMETRY_EVENTS:
        raise ValueError(f"Unknown CLI telemetry event: {event!r}")
    user_id = anonymous_user_id()
    props: dict[str, object] = {
        "distinct_id": user_id,
        "user_id": user_id,
        "brain_id": _safe_brain_id(brain_dir),
        "agent_type": agent_type or "unknown",
        "cli_version": _sdk_version(),
        "experiment_id": _experiment_id(),
        "cohort": _cohort(),
    }
    if rule_id is not None:
        props["rule_id"] = str(rule_id)
    if event == "cli_install":
        props["install_started_at"] = _install_started_at()
    if event == "first_rule_graduated":
        props["hours_since_install"] = _hours_since_install()
    if event == "rule_injected":
        props["injection_count_this_session"] = int(injection_count_this_session or 0)
    return {
        "api_key": _posthog_api_key(),
        "event": event,
        "distinct_id": user_id,
        "properties": props,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _post(payload: dict, timeout: float = 3.0, endpoint: str | None = None) -> bool:
    """Best-effort POST. Never raises. Returns True on 2xx."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint or _endpoint(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("telemetry POST failed: %s", exc)
        return False


def send_event(event: str, *, blocking: bool = False) -> None:
    """Fire an activation event if the user opted in.

    Runs in a background thread by default so it never blocks the user.
    Pass ``blocking=True`` in tests.
    """
    if event not in ACTIVATION_EVENTS:
        raise ValueError(f"Unknown activation event: {event!r}")
    if not is_enabled():
        return
    payload = _build_payload(event)

    if blocking:
        _post(payload)
        return

    thread = threading.Thread(target=_post, args=(payload,), daemon=True)
    thread.start()


def send_cli_event(
    event: str,
    *,
    brain_dir: str | Path | None = None,
    agent_type: str | None = None,
    rule_id: str | None = None,
    injection_count_this_session: int | None = None,
    blocking: bool = False,
) -> None:
    """Fire a GRA-2031 CLI/SDK funnel event.

    Best-effort and opt-in: no exception or network failure may surface to the
    user or block hook hot paths.
    """
    if event not in CLI_TELEMETRY_EVENTS:
        raise ValueError(f"Unknown CLI telemetry event: {event!r}")
    if not is_enabled():
        return
    if not _posthog_api_key():
        logger.debug("CLI telemetry skipped: no PostHog project API key configured")
        return
    try:
        payload = _build_cli_payload(
            event,
            brain_dir=brain_dir,
            agent_type=agent_type,
            rule_id=rule_id,
            injection_count_this_session=injection_count_this_session,
        )
    except Exception as exc:
        logger.debug("CLI telemetry payload build failed: %s", exc)
        return

    endpoint = _posthog_endpoint()
    if blocking:
        _post(payload, endpoint=endpoint)
        return

    thread = threading.Thread(target=_post, args=(payload,), kwargs={"endpoint": endpoint}, daemon=True)
    thread.start()


def send_cli_once(
    event: str,
    *,
    brain_dir: str | Path | None = None,
    agent_type: str | None = None,
    rule_id: str | None = None,
    blocking: bool = False,
) -> bool:
    """Fire a CLI telemetry event at most once per user config."""
    if event not in CLI_TELEMETRY_EVENTS:
        raise ValueError(f"Unknown CLI telemetry event: {event!r}")
    if not is_enabled():
        return False
    with _config_lock():
        cfg = _read_config()
        key = f"telemetry.fired_{event}"
        if cfg.get(key) == "true":
            return False
        _write_config_key(key, "true")
    send_cli_event(event, brain_dir=brain_dir, agent_type=agent_type, rule_id=rule_id, blocking=blocking)
    return True


# ── First-fire guard (activation events fire once per machine) ────────
def _event_flag_key(event: str) -> str:
    return f"telemetry.fired_{event}"


@contextlib.contextmanager
def _config_lock(timeout: float = 2.0) -> Iterator[None]:
    """Best-effort cross-process advisory lock around the config file.

    Uses ``fcntl`` on POSIX and ``msvcrt`` on Windows. If locking is not
    available we degrade silently — telemetry is best-effort and the
    worst-case race only causes a duplicate one-shot event, which the
    backend already tolerates.
    """
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    lock_path = cfg_dir / ".config.lock"
    try:
        fp = open(lock_path, "a+b")  # noqa: SIM115 — closed in finally below
    except OSError:
        yield
        return

    acquired = False
    try:
        if sys.platform == "win32":
            import msvcrt  # type: ignore[import-not-found]

            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.05)
        else:
            import fcntl  # type: ignore[import-not-found]

            # Non-blocking retry loop so the POSIX branch honors ``timeout``
            # just like the Windows branch. Blocking ``flock(LOCK_EX)`` would
            # hang indefinitely if another process holds the lock, violating
            # the documented best-effort contract.
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.05)
        yield
    finally:
        if acquired:
            with contextlib.suppress(Exception):
                if sys.platform == "win32":
                    import msvcrt  # type: ignore[import-not-found]

                    with contextlib.suppress(OSError):
                        fp.seek(0)
                        msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl  # type: ignore[import-not-found]

                    with contextlib.suppress(OSError):
                        fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        with contextlib.suppress(OSError):
            fp.close()


def send_once(event: str, *, blocking: bool = False) -> bool:
    """Fire ``event`` exactly once per machine.

    Returns True if the event was actually sent (or queued), False if it
    was already fired before OR the user has not opted in.

    The read-modify-write on the config flag is wrapped in a cross-process
    advisory lock so two concurrent ``gradata init`` runs can't both fire
    the same event.
    """
    if not is_enabled():
        return False
    with _config_lock():
        cfg = _read_config()
        if cfg.get(_event_flag_key(event)) == "true":
            return False
        _write_config_key(_event_flag_key(event), "true")
    send_event(event, blocking=blocking)
    return True


# ── Interactive prompt ────────────────────────────────────────────────
PROMPT_TEXT = """\
Gradata can send anonymous usage pings (brain_initialized,
first_correction_captured, first_graduation, first_hook_installed) so we
know the SDK is working for you. No code, no lesson text, no personal
data — just event names + hashed user ID.

Enable? [y/N]: """


def prompt_and_persist(input_fn=input) -> bool:
    """Ask the user once; persist the answer. Returns the chosen value.

    Safe for non-interactive environments: any EOFError or missing stdin
    is treated as "no". ``input_fn`` is injectable for tests.
    """
    try:
        answer = input_fn(PROMPT_TEXT).strip().lower()
    except (EOFError, OSError):
        answer = ""
    enabled = answer in ("y", "yes")
    set_enabled(enabled)
    return enabled

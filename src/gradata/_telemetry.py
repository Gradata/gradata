"""Opt-in anonymous SDK activation telemetry. Sends ``{event,
sha256(machine_id), ISO-ts, sdk_version}`` for named events; never lesson/
correction content. Default OFF (opt in via config.toml); ``GRADATA_TELEMETRY
=0`` kill-switch. At most once per machine per install.
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

logger = logging.getLogger("gradata.telemetry")

# ── Constants ─────────────────────────────────────────────────────────
DEFAULT_ENDPOINT: Final[str] = "https://api.gradata.ai/telemetry/event"
ENV_ENDPOINT: Final[str] = "GRADATA_TELEMETRY_ENDPOINT"
ENV_KILL_SWITCH: Final[str] = "GRADATA_TELEMETRY"
_CONFIG_FILENAME: Final[str] = "config.toml"
_ENV_CONFIG_DIR: Final[str] = "GRADATA_CONFIG_DIR"
_ENV_XDG_CONFIG_HOME: Final[str] = "XDG_CONFIG_HOME"


def _config_dir() -> Path:
    """Resolve the user-level Gradata config directory.

    Order: ``GRADATA_CONFIG_DIR`` env override, ``XDG_CONFIG_HOME/gradata``
    on POSIX, else ``~/.gradata``. Does not create the directory.
    """
    override = os.environ.get(_ENV_CONFIG_DIR, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get(_ENV_XDG_CONFIG_HOME, "").strip()
    if xdg and os.name != "nt":
        return (Path(xdg).expanduser() / "gradata").resolve()
    return (Path.home() / ".gradata").resolve()


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

ActivationEvent = Literal[
    "brain_initialized",
    "first_correction_captured",
    "first_graduation",
    "first_hook_installed",
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


def _build_payload(event: str) -> dict[str, str]:
    """Exact wire format. No extra fields, ever."""
    try:
        from . import __version__

        _ver = str(__version__)
    except Exception:
        _ver = "unknown"
    return {
        "event": event,
        "user_id": anonymous_user_id(),
        "ts": datetime.now(UTC).isoformat(),
        "sdk_version": _ver,
    }


def _post(payload: dict[str, str], timeout: float = 3.0) -> bool:
    """Best-effort POST. Never raises. Returns True on 2xx."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _endpoint(),
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

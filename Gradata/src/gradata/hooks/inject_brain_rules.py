"""SessionStart hook: inject graduated rules into session context.

Wiki-aware mode: when brain/wiki/concepts/rule-*.md pages exist,
uses qmd semantic search to find rules relevant to the current
session context instead of brute-force top-10 by confidence.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile
from gradata.rules.rule_ranker import rank_rules

try:
    from gradata.enhancements.self_improvement import is_hook_enforced, parse_lessons
except ImportError:
    parse_lessons = None
    is_hook_enforced = None  # type: ignore[assignment]

try:
    from gradata.enhancements.meta_rules import (
        INJECTABLE_META_SOURCES,
        _lesson_id,
        format_meta_rules_for_prompt,
    )
    from gradata.enhancements.meta_rules_storage import load_meta_rules
except ImportError:
    format_meta_rules_for_prompt = None  # type: ignore[assignment]
    load_meta_rules = None  # type: ignore[assignment]
    _lesson_id = None  # type: ignore[assignment]
    INJECTABLE_META_SOURCES = frozenset()  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# One-shot flag so the qmd-bash-missing warning only fires once per process.
_QMD_BASH_WARNED = False

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.MINIMAL,
    "timeout": 10000,
}

MAX_RULES = int(os.environ.get("GRADATA_MAX_RULES", "10"))
MIN_CONFIDENCE = float(os.environ.get("GRADATA_MIN_CONFIDENCE", "0.60"))
# Meta-rules are high-level principles — separate cap from MAX_RULES.
MAX_META_RULES = int(os.environ.get("GRADATA_MAX_META_RULES", "5"))
MAX_BRAIN_PROMPT_CHARS = int(os.environ.get("GRADATA_MAX_BRAIN_PROMPT_CHARS", "4000"))


def _truncate_prompt_blocks(blocks: list[str], max_chars: int) -> str:
    result_parts: list[str] = []
    used = 0
    for block in blocks:
        if not block:
            continue
        if used + len(block) <= max_chars:
            result_parts.append(block)
            used += len(block)
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        partial = block[:remaining].rstrip()
        close_start = partial.rfind("</")
        if close_start >= 0:
            close_end = partial.find(">", close_start)
            if close_end >= 0:
                partial = partial[: close_end + 1].rstrip()
            else:
                partial = partial[:close_start].rstrip()
        else:
            partial = ""
        if partial:
            result_parts.append(partial)
        break
    return "".join(result_parts).rstrip()


def _filter_injectable_metas(metas: list) -> list:
    injectable = []
    for m in metas:
        source = getattr(m, "source", "deterministic")
        if source in INJECTABLE_META_SOURCES:
            injectable.append(m)
        else:
            _log.warning(
                "dropping meta-rule %s (source=%s) from injection",
                getattr(m, "id", "<unknown>"),
                source,
            )
    return injectable


# Sentinel written by inject_handoff when a handoff carries a rules snapshot.
# When present, we compare mtime(lessons.md) vs. snapshot_ts and skip the
# ranked <brain-rules> block if nothing has graduated since — the handoff
# already carries the prior agent's operating rules implicitly.
_HANDOFF_ACTIVE_FILE = ".handoff_active.json"


def _should_skip_ranked_rules(brain_dir: Path, lessons_path: Path) -> bool:
    """Return True when a fresh handoff carries the current rule snapshot.

    Consumes the sentinel on read so subsequent sessions re-inject normally
    unless a new handoff was produced. Any parse/IO error returns False so
    injection behaves exactly as before — this is a pure optimization layer.
    """
    if os.environ.get("GRADATA_HANDOFF_RULES_DELTA", "1") != "1":
        return False
    sentinel = brain_dir / _HANDOFF_ACTIVE_FILE
    if not sentinel.is_file():
        return False
    try:
        import json as _json

        payload = _json.loads(sentinel.read_text(encoding="utf-8"))
        snapshot_iso = str(payload.get("rules_snapshot_ts") or "")
        if not snapshot_iso:
            return False
        snapshot = datetime.fromisoformat(snapshot_iso)
        lessons_mtime = datetime.fromtimestamp(lessons_path.stat().st_mtime, tz=UTC)
        unchanged = lessons_mtime <= snapshot
    except (OSError, ValueError, KeyError) as exc:
        _log.debug("handoff sentinel parse failed (%s) — falling back", exc)
        return False
    finally:
        with contextlib.suppress(OSError):
            sentinel.unlink()
    return unchanged


def _score(lesson) -> float:
    """Back-compat scorer. Kept so existing tests / callers keep working.

    Prefer :func:`rank_rules` directly for new code — it supports BM25 context
    relevance and optional Thompson sampling. This function is a simple
    state/confidence blend retained for tie-breaking snapshots.
    """
    conf = lesson["confidence"] if isinstance(lesson, dict) else lesson.confidence
    state = lesson["state"] if isinstance(lesson, dict) else lesson.state.name
    conf_norm = (conf - MIN_CONFIDENCE) / (1.0 - MIN_CONFIDENCE)
    state_bonus = 1.0 if state == "RULE" else 0.7
    return 0.4 * state_bonus + 0.3 * conf_norm + 0.3 * conf


_BRAIN_PROMPT_MARKER = "AUTO-GENERATED"


def _read_brain_prompt(brain_dir: Path) -> str | None:
    """Return the `<brain-wisdom>`-wrapped brain_prompt.md body, or None.

    Accepts the file only when it carries the AUTO-GENERATED marker written
    by session_close._refresh_brain_prompt — files without the marker are
    assumed to be stale hand-edits or test fixtures and are ignored. Wraps
    the body in `<brain-wisdom>` if not already present. Returns None on
    missing file, missing marker, empty body, or read error.
    """
    bp = brain_dir / "brain_prompt.md"
    if not bp.is_file():
        return None
    try:
        text = bp.read_text(encoding="utf-8").strip()
    except OSError as exc:
        _log.debug("brain_prompt.md read failed (%s) — falling back", exc)
        return None
    if not text or _BRAIN_PROMPT_MARKER not in text[:400]:
        return None
    # Strip XML/HTML comments — they carry no semantic signal for the LLM and
    # cost ~40 tokens per session start (measured 2026-04-21 autoresearch loop).
    import re as _re

    text = _re.sub(r"<!--.*?-->", "", text, flags=_re.DOTALL).strip()
    # Replace verbose <brain-wisdom>…</brain-wisdom> wrapper with compact [wisdom]
    # marker — saves 8 tokens per session start with identical LLM semantics.
    text = _re.sub(r"<brain-wisdom>\s*", "", text)
    text = _re.sub(r"\s*</brain-wisdom>", "", text).strip()
    # Strip **bold** markdown markers — they add ~5 tokens for zero semantic gain.
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Collapse indented sub-bullets (`  - item`) into inline `;`-separated suffixes.
    # E.g. `- Lead handling:\n  - A\n  - B` → `- Lead handling: A; B`
    # Saves ~12 tokens per session start (measured 2026-04-21 autoresearch loop).
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        sub_items: list[str] = []
        j = i + 1
        while j < len(lines) and lines[j].startswith("  - "):
            sub_items.append(lines[j][4:])
            j += 1
        if sub_items:
            parent = line.rstrip(":")
            result.append(parent + ": " + "; ".join(sub_items))
            i = j
        else:
            result.append(line)
            i += 1
    text = "\n".join(result)
    # Active guidance + Current disposition sections kept by default — they
    # carry softer behavioral context the model needs at session start. Set
    # GRADATA_WISDOM_FULL=0 to strip them (ablation only).
    if os.environ.get("GRADATA_WISDOM_FULL", "1") != "1":
        for marker in ("Active guidance", "Current disposition"):
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx].rstrip()
                break
    # Compress verbose section header — saves 8 tokens per session.
    # "Non-negotiables (response rejected if violated):" → "MUST:"
    text = _re.sub(
        r"Non-negotiables?\s*\([^)]*\)\s*:",
        "MUST:",
        text,
        count=1,
    )
    # Limit to first GRADATA_WISDOM_MAX_RULES non-negotiable rules.
    _raw_max = os.environ.get("GRADATA_WISDOM_MAX_RULES", "9")
    try:
        wisdom_max_rules = int(_raw_max)
    except (ValueError, TypeError):
        _log.warning("GRADATA_WISDOM_MAX_RULES=%r not an int — defaulting to 9", _raw_max)
        wisdom_max_rules = 9
    if wisdom_max_rules > 0:
        rule_lines = [ln for ln in text.split("\n") if ln.startswith("- ")]
        if len(rule_lines) > wisdom_max_rules:
            # Find the character position just after the Nth rule line.
            remaining = wisdom_max_rules
            cutoff = len(text)
            for j, _ch in enumerate(text):
                if text[j : j + 2] == "- " and j > 0 and text[j - 1] == "\n":
                    remaining -= 1
                    if remaining < 0:
                        cutoff = j
                        break
            text = text[:cutoff].rstrip()
    # Truncate body before wrapping (safety net — rule-limit above is primary).
    if len(text) > MAX_BRAIN_PROMPT_CHARS:
        text = text[:MAX_BRAIN_PROMPT_CHARS]
    # Drop the [wisdom] wrapper — section header (MUST:) is self-explanatory.
    # Saves 4 tokens per session start (measured 2026-04-21 autoresearch loop).
    return text


def _lesson_to_rule_dict(lesson, current_session: int = 0) -> dict:
    """Flatten a Lesson object (or dict) into the shape rank_rules expects.

    Carries Beta posterior fields (alpha / beta_param) through so Thompson
    sampling works when ``GRADATA_THOMPSON_RANKING=1``.

    ``last_session`` is derived as ``current_session - sessions_since_fire``
    when both are known — rule_ranker._recency_score expects absolute session
    numbers, and before this we were hard-coding 0 which killed the recency
    component of the ranker entirely. Falls back to 0 (neutral) when the
    caller doesn't pass current_session or sessions_since_fire is unset.
    """
    if isinstance(lesson, dict):
        d = dict(lesson)
        d.setdefault("last_session", 0)
        return d
    sessions_since = int(getattr(lesson, "sessions_since_fire", 0) or 0)
    if current_session > 0 and sessions_since >= 0:
        last_session = max(0, current_session - sessions_since)
    else:
        last_session = 0
    return {
        "id": getattr(lesson, "description", ""),
        "description": getattr(lesson, "description", ""),
        "category": getattr(lesson, "category", ""),
        "confidence": float(getattr(lesson, "confidence", 0.5)),
        "fire_count": int(getattr(lesson, "fire_count", 0)),
        "last_session": last_session,
        "alpha": float(getattr(lesson, "alpha", 1.0)),
        "beta_param": float(getattr(lesson, "beta_param", 1.0)),
        "state": lesson.state.name if hasattr(lesson, "state") else "PATTERN",
        "_lesson": lesson,  # stash original for output formatting
    }


def _wiki_categories(context: str) -> set[str]:
    """Query qmd for rule wiki pages matching context, return matched categories.

    Searches brain wiki for pages whose path matches rule-{category}.md.
    Returns empty set on any failure so caller falls back to brute-force.
    """
    if not context:
        return set()
    # On Windows, qmd is an npm bash script — Python can't exec .CMD wrappers
    # directly, so we route through Git Bash. On Unix, qmd runs natively.
    if sys.platform == "win32":
        git_bash = shutil.which("bash", path="C:/Program Files/Git/bin")
        if git_bash:
            cmd = [git_bash, "-c", f'qmd search "{context}" -c brain -n 10']
        else:
            # Loud fallback: wiki-aware routing is silently disabled without
            # Git Bash on Windows, and a silent failure hides a real capability
            # gap. Emit once per process via a module-level flag.
            global _QMD_BASH_WARNED
            if not _QMD_BASH_WARNED:
                _log.warning(
                    "qmd wiki-aware routing disabled: Git Bash not found at "
                    "C:/Program Files/Git/bin. Install Git for Windows or set "
                    "PATH, or category routing will fall back to brute-force."
                )
                _QMD_BASH_WARNED = True
            return set()
    else:
        cmd = ["qmd", "search", context, "-c", "brain", "-n", "10"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            return set()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return set()

    categories: set[str] = set()
    for line in proc.stdout.splitlines():
        # qmd paths: qmd://brain/wiki/concepts/rule-code.md:N
        if "wiki/concepts/rule-" in line:
            try:
                segment = line.split("wiki/concepts/rule-")[1]
                cat = segment.split(".md")[0].upper().replace("-", "_")
                categories.add(cat)
            except (IndexError, ValueError):
                continue
    return categories


def main(data: dict) -> dict | None:
    if parse_lessons is None:
        return None

    # Skip re-injection on compact/resume: the compacted summary already
    # carries rules from the prior session, and the new session's primacy
    # slot is consumed by the summary itself. Re-firing here duplicates
    # ~1.9KB per compact event (measured 10x in a long session = ~3.7k tok).
    # Opt back in with GRADATA_INJECT_ON_COMPACT=1 for ablation.
    if os.environ.get("GRADATA_INJECT_ON_COMPACT", "0") != "1":
        source = str(data.get("source", "") or "").lower()
        if source in ("compact", "resume"):
            return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None
    try:
        from gradata._config import _load_brain_config

        brain_cfg = _load_brain_config(brain_dir)
    except ImportError:
        brain_cfg = None
    max_rules = MAX_RULES
    max_prompt_chars = MAX_BRAIN_PROMPT_CHARS
    if brain_cfg is not None:
        max_prompt_chars = min(max_prompt_chars, brain_cfg.max_recall_tokens * 4)

    lessons_path = Path(brain_dir) / "lessons.md"
    if not lessons_path.is_file():
        return None

    text = lessons_path.read_text(encoding="utf-8")
    all_lessons = parse_lessons(text)
    filtered = [
        lesson
        for lesson in all_lessons
        if lesson.state.name in ("RULE", "PATTERN") and lesson.confidence >= MIN_CONFIDENCE
    ]
    # Phase 5 rule-to-hook auto-promotion: rules enforced by an installed
    # generated hook (metadata.how_enforced == "hooked", or legacy "[hooked]"
    # description prefix) are applied deterministically, so injecting them as
    # text wastes context. Hook removal clears the marker and re-enables text
    # injection automatically.
    if is_hook_enforced is not None:
        filtered = [lesson for lesson in filtered if not is_hook_enforced(lesson)]
    if not filtered:
        return None

    # Handoff-delta optimization: when a fresh handoff carried a rules
    # snapshot timestamp and lessons.md has not changed since, the prior
    # agent already operated under these rules — suppress the ranked block
    # to avoid re-paying the injection cost. Mandatory / disposition /
    # meta-rules / brain_prompt paths still fire as normal.
    skip_ranked_rules = _should_skip_ranked_rules(Path(brain_dir), lessons_path)

    # Wiki-aware selection: find categories relevant to session context
    context = data.get("session_type", "") or data.get("task_type", "") or Path.cwd().name
    wiki_cats = _wiki_categories(context)

    # Route everything through the unified rule_ranker. Wiki-matched categories
    # become a wiki_boost signal (+0.3 on context component) rather than a
    # hard pre-filter, so BM25 + Thompson can still surface strong cross-
    # category matches when the wiki miss-matches.
    current_session_number = int(data.get("session_number") or 0)
    rule_dicts = [_lesson_to_rule_dict(lesson, current_session_number) for lesson in filtered]
    wiki_boost: dict[str, float] = {}
    if wiki_cats:
        for rd in rule_dicts:
            if rd.get("category", "").upper() in wiki_cats:
                wiki_boost[rd["id"]] = 0.3

    context_keywords = [
        kw
        for kw in (
            data.get("session_type", ""),
            data.get("task_type", ""),
            context,
        )
        if kw
    ]

    # Derive a per-session seed for deterministic Thompson sampling.
    session_seed = data.get("session_number") or data.get("session_id")
    if isinstance(session_seed, str):
        try:
            session_seed = int(session_seed)
        except ValueError:
            session_seed = abs(hash(session_seed)) % (2**31)

    # Overshoot the ranker so cluster/meta mutex filters have refill candidates.
    # Without this, the ranker hard-caps at MAX_RULES and any rule suppressed
    # by a cluster or meta-rule leaves an empty slot that cannot be filled.
    # Final render loop enforces the MAX_RULES budget after filtering.
    rank_overshoot = max(max_rules * 3, max_rules + 10)
    ranked = rank_rules(
        rule_dicts,
        current_session=int(data.get("session_number") or 0),
        task_type=data.get("task_type") or data.get("session_type") or None,
        context_keywords=context_keywords or None,
        max_rules=rank_overshoot,
        wiki_boost=wiki_boost or None,
        session_seed=session_seed if isinstance(session_seed, int) else None,
    )
    scored: list = []
    for rd in ranked:
        lesson = rd.get("_lesson")
        if lesson is not None:
            scored.append(lesson)
    _log.debug(
        "Unified injection: %d ranked (wiki_boost=%d)",
        len(scored),
        len(wiki_boost),
    )

    # Cluster-level injection: replace groups of related rules with summaries.
    # For clusters with confidence >= 0.75 and size >= 3 (and no contradictions),
    # inject one summary line instead of each individual member rule.
    # This reduces total injection slot usage while preserving semantic density.
    # Sanitize lesson/rule text before embedding in XML.
    # A lesson containing "</brain-rules>" would terminate the block early and
    # allow injection of arbitrary content into the agent context.
    from gradata.enhancements._sanitize import sanitize_lesson_content

    # Mutex: pre-compute categories that already have an injectable meta-rule.
    # When a meta-rule covers a category, suppress the cluster for that category
    # to avoid double-injection (cluster summary + meta-rule principle = redundant).
    # Individual rules are unaffected — they remain valuable as concrete examples
    # alongside the abstract principle.
    # Cached: the meta-rule loader is reused below in the formatter block to
    # avoid a second DB open + deserialization pass.
    meta_covered_categories: set[str] = set()
    meta_covered_lesson_ids: set[str] = set()
    cached_metas: list | None = None
    cached_injectable_metas: list | None = None
    db_path = Path(brain_dir) / "system.db"
    if load_meta_rules and db_path.is_file():
        try:
            cached_metas = list(load_meta_rules(db_path))
            cached_injectable_metas = _filter_injectable_metas(cached_metas)
            for m in cached_injectable_metas:
                meta_covered_categories.update(getattr(m, "source_categories", []))
                meta_covered_lesson_ids.update(getattr(m, "source_lesson_ids", []) or [])
        except Exception as exc:
            _log.debug("meta-rule mutex pre-pass failed (%s) — clusters will fire", exc)
            cached_metas = None
            cached_injectable_metas = None

    # Injection manifest: short_anchor → {full_id, category, description, state,
    # cluster_category}. Written to <brain>/.last_injection.json so the
    # correction-capture hook can attribute misfires to specific rules inside
    # clusters rather than to the cluster as a whole (Meta-Harness A).
    injection_manifest: dict[str, dict] = {}
    # Build lookup from the cluster member_ids string format back to Lesson.
    # Format matches clustering.py: f"{l.category}:{l.description[:40]}".
    _lesson_by_member_id = {f"{l.category}:{l.description[:40]}": l for l in filtered}

    def _anchor_for(lesson) -> str | None:
        """4-char stable anchor for a Lesson. None if _lesson_id unavailable."""
        if _lesson_id is None:
            return None
        try:
            return _lesson_id(lesson)[:4]
        except Exception:
            return None

    cluster_injected_ids: set[str] = set()
    cluster_lines: list[str] = []
    try:
        from gradata.enhancements.clustering import cluster_rules

        clusters = cluster_rules(filtered, min_cluster_size=3)
        for cluster in clusters:
            if cluster.category in meta_covered_categories:
                _log.debug(
                    "Cluster mutex: skipping cluster for %s (covered by meta-rule)",
                    cluster.category,
                )
                continue
            if cluster.cluster_confidence >= 0.75 and not cluster.has_contradictions:
                safe_summary = sanitize_lesson_content(cluster.summary, "xml")
                safe_category = sanitize_lesson_content(cluster.category, "xml")
                member_anchors: list[str] = []
                for mid in cluster.member_ids:
                    member_lesson = _lesson_by_member_id.get(mid)
                    if member_lesson is None:
                        continue
                    anchor = _anchor_for(member_lesson)
                    if anchor is None or _lesson_id is None:
                        continue
                    member_anchors.append(anchor)
                    injection_manifest[anchor] = {
                        "full_id": _lesson_id(member_lesson),
                        "category": member_lesson.category,
                        "description": member_lesson.description,
                        "state": member_lesson.state.name,
                        "cluster_category": cluster.category,
                    }
                anchor_suffix = f" r:{','.join(member_anchors)}" if member_anchors else ""
                cluster_lines.append(
                    f"[CLUSTER:{cluster.cluster_confidence:.2f}|×{cluster.size}"
                    f"{anchor_suffix}] {safe_category}: {safe_summary}"
                )
                cluster_injected_ids.update(cluster.member_ids)
    except ImportError:
        pass

    _log.debug(
        "Cluster injection: %d clusters replaced %d individual rules",
        len(cluster_lines),
        len(cluster_injected_ids),
    )

    # Individual rules: only those NOT already covered by a qualifying cluster
    # OR by an injectable meta-rule. Meta-rule mutex suppresses leaves whose
    # abstract principle is already carried by an injected meta — avoids the
    # "meta says X / leaf says X (example)" double-spend on injection slots.
    # Opt out with GRADATA_META_RULE_MUTEX=0 for ablation.
    lesson_id_fn = _lesson_id
    meta_mutex_enabled = (
        lesson_id_fn is not None
        and meta_covered_lesson_ids
        and os.environ.get("GRADATA_META_RULE_MUTEX", "1") == "1"
    )
    suppressed_by_meta = 0
    individual_lines: list[str] = []
    # Total <brain-rules> entries = cluster_lines + individual_lines.
    # Enforce MAX_RULES here (after mutex) so freed slots get refilled from
    # the overshoot pool, and the final block still respects the budget.
    render_budget = max(0, max_rules - len(cluster_lines))
    for r in scored:
        if len(individual_lines) >= render_budget:
            break
        rule_id = f"{r.category}:{r.description[:40]}"
        if rule_id in cluster_injected_ids:
            continue
        if (
            meta_mutex_enabled
            and lesson_id_fn is not None
            and lesson_id_fn(r) in meta_covered_lesson_ids
        ):
            suppressed_by_meta += 1
            continue
        safe_desc = sanitize_lesson_content(r.description, "xml")
        safe_cat = sanitize_lesson_content(r.category, "xml")
        anchor = _anchor_for(r)
        anchor_suffix = f" r:{anchor}" if anchor else ""
        individual_lines.append(
            f"[{r.state.name}:{r.confidence:.2f}{anchor_suffix}] {safe_cat}: {safe_desc}"
        )
        if anchor and _lesson_id is not None:
            injection_manifest[anchor] = {
                "full_id": _lesson_id(r),
                "category": r.category,
                "description": r.description,
                "state": r.state.name,
                "cluster_category": None,
            }
    if suppressed_by_meta:
        _log.debug(
            "Meta-rule mutex: suppressed %d leaf rules covered by injected metas",
            suppressed_by_meta,
        )

    # Feed the selected rules into the slot-grouped synthesizer (Preston-Rhodes
    # 6-step: task -> context -> examples -> persona -> format -> tone). Emits
    # inline r:xxxx anchors whose 4-char keys match injection_manifest, so
    # capture_learning.py attribution still works.
    if skip_ranked_rules:
        rules_block = ""
    else:
        synth_input: list[dict] = []
        for r in scored[:max_rules]:
            if (
                meta_mutex_enabled
                and lesson_id_fn is not None
                and lesson_id_fn(r) in meta_covered_lesson_ids
            ):
                continue
            rid = lesson_id_fn(r) if lesson_id_fn is not None else ""
            synth_input.append(
                {
                    "category": r.category,
                    "description": sanitize_lesson_content(r.description, "xml"),
                    "rule_id": rid,
                    "slot": getattr(r, "slot", "") or "",
                    "example_draft": getattr(r, "example_draft", None),
                    "example_corrected": getattr(r, "example_corrected", None),
                }
            )

        if synth_input:
            from gradata.enhancements.prompt_synthesizer import synthesize_brain_injection

            persona_path = Path(brain_dir).parent / "domain" / "soul.md"
            synth = synthesize_brain_injection(
                synth_input,
                persona_baseline=persona_path if persona_path.is_file() else None,
            )
            rules_block = f"<brain-rules>\n{synth.text}\n</brain-rules>" if synth.text else ""
        else:
            rules_block = ""

    # Persist injection manifest so correction-capture can attribute misfires
    # to specific rules (Meta-Harness A). Silent failure: missing manifest
    # just disables per-rule attribution, never blocks session start.
    if injection_manifest:
        try:
            import json as _json

            manifest_path = Path(brain_dir) / ".last_injection.json"
            manifest_path.write_text(
                _json.dumps(
                    {"anchors": injection_manifest},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            _log.debug("injection manifest write failed: %s", exc)

    # lesson_applications PENDING rows — one per injected rule/cluster member.
    # Closes the compound-quality audit gap: without these, no row proves a
    # graduated rule ever fired. session_close resolves them to
    # CONFIRMED/REJECTED based on correction activity in the same session.
    if (
        injection_manifest
        and db_path.is_file()
        and lesson_id_fn is not None
        and not skip_ranked_rules
    ):
        try:
            import json as _json

            from gradata._db import get_connection

            applied_at = datetime.now(UTC).isoformat()
            session_num = int(data.get("session_number") or 0)
            task_context = (context or "")[:200]
            rows = []
            for entry in injection_manifest.values():
                ctx_blob = _json.dumps(
                    {
                        "category": entry.get("category", ""),
                        "description": entry.get("description", "")[:200],
                        "task": task_context,
                    }
                )
                rows.append((entry["full_id"], session_num, applied_at, ctx_blob, "PENDING", 1))
            if rows:
                conn = get_connection(db_path)
                try:
                    conn.executemany(
                        "INSERT INTO lesson_applications "
                        "(lesson_id, session, applied_at, context, outcome, success) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.OperationalError as exc:
            _log.warning("lesson_applications write failed (schema issue?): %s", exc)
        except Exception as exc:
            _log.debug("lesson_applications write failed: %s", exc)

    # Inject disposition (behavioral tendencies evolved from corrections)
    disposition_block = ""
    try:
        from gradata.enhancements.behavioral_engine import DispositionTracker

        tracker = DispositionTracker()
        # Load disposition from brain dir if persisted
        disp_path = Path(brain_dir) / "disposition.json"
        if disp_path.is_file():
            import json as _json

            tracker = DispositionTracker.from_dict(
                _json.loads(disp_path.read_text(encoding="utf-8"))
            )
        domain = context or "global"
        disp = tracker.get(domain)
        instructions = disp.behavioral_instructions()
        if instructions:
            disposition_block = (
                "\n<brain-disposition>\n" + disp.format_for_prompt() + "\n</brain-disposition>"
            )
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("Disposition injection failed: %s", exc)

    # Mandatory injection tier: RULE confidence >= 0.90 AND fire_count >= 10.
    # These appear in a separate primacy block AND a recency reminder so they
    # always fire regardless of how the model processes the brain-rules section.
    # Mandatory rules are intentionally NOT excluded from ranked scoring above —
    # they appear in both mandatory block and may appear in brain-rules.
    mandatory = [
        lesson
        for lesson in all_lessons
        if lesson.state.name == "RULE"
        and lesson.confidence >= 0.90
        and getattr(lesson, "fire_count", 0) >= 10
    ]
    mandatory_lines: list[str] = [f"[MANDATORY] {r.category}: {r.description}" for r in mandatory]
    if mandatory_lines:
        mandatory_block = (
            "<mandatory-directives>\n"
            "## NON-NEGOTIABLE DIRECTIVES\n"
            "These rules are MANDATORY. Your response will be REJECTED if any are violated.\n"
            + "\n".join(mandatory_lines)
            + "\n</mandatory-directives>"
        )
    else:
        mandatory_block = ""

    # Also inject tier-1 meta-rules (compound principles across 3+ lessons).
    # Without this, meta-rules are created + stored but never reach the LLM.
    # Quality gate: only inject metas whose principle text was LLM-synthesized
    # or human-curated. Deterministic auto-generated principles (the OSS
    # default) are excluded — the 2026-04-14 ablation (432 trials) showed they
    # regress correctness on Sonnet (-1.1%), DeepSeek (-1.4%), and halve the
    # qwen14b lift from +8.1% to +2.9%. Better to inject nothing than noise.
    meta_block = ""
    if load_meta_rules and format_meta_rules_for_prompt and db_path.is_file():
        # Wrap the entire load -> filter -> format pipeline. A partially corrupt
        # system.db can deserialize successfully (e.g. JSON `null` for
        # source_lesson_ids) and then blow up later with TypeError inside the
        # formatter. We must degrade to rules-only rather than aborting
        # SessionStart.
        try:
            # Reuse the mutex pre-pass result when available to avoid a second
            # DB open. Fall back to a fresh load if the pre-pass failed.
            if cached_injectable_metas is not None:
                injectable = cached_injectable_metas
                meta_count = len(cached_metas or [])
            else:
                fresh_metas = list(load_meta_rules(db_path))
                injectable = _filter_injectable_metas(fresh_metas)
                meta_count = len(fresh_metas)
            if injectable:
                # Build a sanitized condition_context from the hook payload so
                # applies_when / never_when are honored during SessionStart.
                # We only forward small, string-shaped fields the rule engine
                # uses for gating — no file contents, transcripts, or secrets.
                condition_context = {
                    k: data[k]
                    for k in ("session_type", "task_type", "source", "cwd")
                    if isinstance(data.get(k), (str, int, float, bool))
                }
                if context and "context" not in condition_context:
                    condition_context["context"] = context

                # Pass the full injectable set with `limit=MAX_META_RULES` so
                # the cap is applied AFTER context-aware ranking inside the
                # formatter. Pre-slicing by raw confidence would let a
                # lower-confidence rule with a strong context weight get
                # silently excluded.
                formatted = format_meta_rules_for_prompt(
                    injectable,
                    context=context,
                    condition_context=condition_context,
                    limit=MAX_META_RULES,
                )
                if formatted:
                    meta_block = "\n<brain-meta-rules>\n" + formatted + "\n</brain-meta-rules>"
            elif meta_count:
                _log.debug(
                    "Skipped meta-rule injection: %d metas in DB, none with "
                    "injectable source (llm_synth or human_curated)",
                    meta_count,
                )
        except Exception as exc:
            _log.debug(
                "meta-rule pipeline failed (%s) — degrading to rules-only",
                exc,
            )
            meta_block = ""

    # Persistent brain-prompt: if brain/brain_prompt.md exists AND was written
    # by session_close._refresh_brain_prompt (identified by the AUTO-GENERATED
    # header), inject it verbatim and skip the fragmented composition.
    # Synthesis never runs in the injection hook — that path was slow (CLI
    # round-trip) and non-deterministic. The session_close hook is the only
    # place we call the LLM; injection is pure read-compose.
    bp_text = _read_brain_prompt(Path(brain_dir))
    if bp_text:
        if len(bp_text) > max_prompt_chars:
            bp_text = bp_text[:max_prompt_chars].rstrip()
        return {"result": bp_text}

    result = _truncate_prompt_blocks(
        [mandatory_block, disposition_block, rules_block, meta_block],
        max_prompt_chars,
    )
    return {"result": result}


if __name__ == "__main__":
    run_hook(main, HOOK_META)

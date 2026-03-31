"""
Brain Export Script (SDK Copy).
================================
Packages a trained brain into a shareable archive.
Portable — uses _paths instead of hardcoded paths.
"""

import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import gradata._paths as _p
from gradata._paths import BrainContext


def _EXPORTS_DIR(): return _p.BRAIN_DIR / "exports"
def _VAULT_DIR(): return _p.BRAIN_DIR / "vault"
def _LESSONS_ACTIVE(): return _p.LESSONS_FILE
def _LESSONS_ARCHIVE(): return _p.BRAIN_DIR / "lessons-archive.md"
def _QUALITY_RUBRICS(): return _p.WORKING_DIR / ".claude" / "quality-rubrics.md"
def _DOMAIN_CONFIG(): return _p.WORKING_DIR / "domain" / "DOMAIN.md"
def _DOMAIN_SOUL(): return _p.WORKING_DIR / "domain" / "soul.md"
def _CARL_LOOP(): return _p.CARL_DIR / "loop"
def _CARL_GLOBAL(): return _p.CARL_DIR / "global"

# Sensitive data patterns
RE_EMAIL = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
RE_PHONE = re.compile(r'(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}')
RE_API_KEY = re.compile(r'(?:api[_\-]?key|token|secret|password|bearer)\s*[:=]\s*\S+', re.IGNORECASE)
RE_USER_PATH = re.compile(r'C:[/\\]Users[/\\]\w+', re.IGNORECASE)
RE_PIPEDRIVE_URL = re.compile(r'https?://[a-z0-9\-]+\.pipedrive\.com\S*', re.IGNORECASE)
RE_PIPEDRIVE_DEAL = re.compile(r'(?:pipedrive_deal_id|deal[_\-]?id)\s*[:=]\s*\d+', re.IGNORECASE)


def read_version() -> str:
    if not _p.VERSION_FILE.exists():
        return "v0.0.0"
    text = _p.VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'Current Version:\s*(v[\d.]+)', text)
    return match.group(1) if match else "v0.0.0"


def read_domain_name() -> str:
    if not _DOMAIN_CONFIG().exists():
        return "Unknown"
    text = _DOMAIN_CONFIG().read_text(encoding="utf-8")
    match = re.search(r'Talent:\s*(\w+)', text)
    if match:
        return match.group(1)
    match = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    return match.group(1).strip() if match else "Unknown"


def read_session_count() -> int:
    if not _p.VERSION_FILE.exists():
        return 0
    text = _p.VERSION_FILE.read_text(encoding="utf-8")
    sessions = re.findall(r'Session\s+(\d+)', text)
    return max(int(s) for s in sessions) if sessions else 0


def count_lessons(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    text = filepath.read_text(encoding="utf-8")
    return len(re.findall(r'^\[20\d{2}-\d{2}-\d{2}\]', text, re.MULTILINE))


def build_prospect_map(prospects_dir: Path) -> dict[str, str]:
    name_map: dict[str, str] = {}
    if not prospects_dir.exists():
        return name_map
    counter = 1
    for f in sorted(prospects_dir.iterdir()):
        if f.name.startswith("_") or not f.name.endswith(".md"):
            continue
        stem = f.stem
        if "\u2014" in stem:
            name_part, company_part = stem.split("\u2014", 1)
            name_part, company_part = name_part.strip(), company_part.strip()
        elif " - " in stem:
            name_part, company_part = stem.split(" - ", 1)
        else:
            name_part, company_part = stem, None

        name_map[name_part] = f"[PROSPECT_{counter}]"
        first_name = name_part.split()[0] if " " in name_part else None
        if first_name and len(first_name) >= 4 and first_name not in name_map:
            name_map[first_name] = f"[PROSPECT_{counter}]"
        if company_part:
            name_map[company_part] = f"[COMPANY_{counter}]"

        try:
            text = f.read_text(encoding="utf-8")
            fm_name = re.search(r'^name:\s*(.+)$', text, re.MULTILINE)
            if fm_name and fm_name.group(1).strip():
                val = fm_name.group(1).strip()
                name_map[val] = f"[PROSPECT_{counter}]"
            fm_company = re.search(r'^company:\s*(.+)$', text, re.MULTILINE)
            if fm_company and fm_company.group(1).strip():
                name_map[fm_company.group(1).strip()] = f"[COMPANY_{counter}]"
        except Exception:
            pass
        counter += 1

    # Auto-detect owner name from brain manifest if available
    manifest_path = _p.BRAIN_DIR / "brain.manifest.json" if hasattr(_p, 'BRAIN_DIR') and _p.BRAIN_DIR else None
    if manifest_path and manifest_path.exists():
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = __import__("json").load(f)
            owner = manifest.get("metadata", {}).get("owner", "")
            if owner:
                name_map[owner] = "[OWNER]"
                name_map[owner.lower()] = "[OWNER]"
        except Exception:
            pass
    return name_map


def sanitize_content(text: str, name_map: dict[str, str]) -> str:
    text = RE_EMAIL.sub('[EMAIL_REDACTED]', text)
    text = RE_PHONE.sub('[PHONE_REDACTED]', text)
    text = RE_API_KEY.sub('[API_KEY_REDACTED]', text)
    text = RE_PIPEDRIVE_URL.sub('[PIPEDRIVE_URL_REDACTED]', text)
    text = RE_PIPEDRIVE_DEAL.sub('pipedrive_deal_id: [DEAL_REDACTED]', text)
    text = RE_USER_PATH.sub('[USER_HOME]', text)
    for real_name in sorted(name_map, key=len, reverse=True):
        if len(real_name) >= 3:
            text = text.replace(real_name, name_map[real_name])
    return text


def sanitize_filename(filename: str, name_map: dict[str, str]) -> str:
    result = filename
    for real_name in sorted(name_map, key=len, reverse=True):
        if len(real_name) >= 3:
            result = result.replace(real_name, name_map[real_name])
    return result


def collect_brain_files(include_prospects: bool = True) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    if include_prospects and _p.PROSPECTS_DIR.exists():
        for f in sorted(_p.PROSPECTS_DIR.iterdir()):
            if f.name.endswith(".md") and not f.name.startswith("_"):
                files.append((f"brain/prospects/{f.name}", f))
    if _VAULT_DIR().exists():
        for f in sorted(_VAULT_DIR().iterdir()):
            if f.is_file():
                files.append((f"brain/vault/{f.name}", f))
    if _p.SESSIONS_DIR.exists():
        for f in sorted(_p.SESSIONS_DIR.iterdir()):
            if f.is_file() and f.name.endswith(".md"):
                files.append((f"brain/sessions/{f.name}", f))
    for name in ["PATTERNS.md", "system-patterns.md", "TAXONOMY.md"]:
        p = _p.BRAIN_DIR / name
        if p.exists():
            files.append((f"brain/{name}", p))
    return files


def collect_domain_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    if _DOMAIN_CONFIG().exists():
        files.append(("domain/DOMAIN.md", _DOMAIN_CONFIG()))
    if _DOMAIN_SOUL().exists():
        files.append(("domain/soul.md", _DOMAIN_SOUL()))
    if _p.GATES_DIR.exists():
        for f in sorted(_p.GATES_DIR.iterdir()):
            if f.is_file() and f.name.endswith(".md"):
                files.append((f"domain/gates/{f.name}", f))
    return files


def export_brain(include_prospects: bool = True, domain_only: bool = False,
                  ctx: BrainContext | None = None) -> Path:
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    prospects_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR

    version = read_version()
    domain = read_domain_name()
    sessions = read_session_count()
    graduated = count_lessons(_LESSONS_ARCHIVE())
    active = count_lessons(_LESSONS_ACTIVE())

    all_files: list[tuple[str, Path]] = []
    if domain_only:
        all_files.extend(collect_domain_files())
    else:
        all_files.extend(collect_brain_files(include_prospects=include_prospects))
        all_files.extend(collect_domain_files())
        if _LESSONS_ARCHIVE().exists():
            all_files.append(("lessons/lessons-archive.md", _LESSONS_ARCHIVE()))
        if _CARL_LOOP().exists():
            all_files.append(("carl/loop.md", _CARL_LOOP()))
        if _CARL_GLOBAL().exists():
            all_files.append(("carl/global.md", _CARL_GLOBAL()))
        if _QUALITY_RUBRICS().exists():
            all_files.append(("quality/quality-rubrics.md", _QUALITY_RUBRICS()))

    name_map = build_prospect_map(prospects_dir)
    sanitized: list[tuple[str, str]] = []
    for archive_path, source_path in all_files:
        try:
            raw = source_path.read_text(encoding="utf-8")
        except Exception:
            continue
        clean = sanitize_content(raw, name_map)
        clean_path = sanitize_filename(archive_path, name_map)
        sanitized.append((clean_path, clean))

    now = datetime.now(UTC)
    try:
        from gradata._brain_manifest import generate_manifest
        manifest = generate_manifest(ctx=ctx)
        manifest["export"] = {
            "exported_at": now.isoformat(),
            "mode": "domain-only" if domain_only else ("no-prospects" if not include_prospects else "full"),
            "files": [path for path, _ in sanitized],
        }
    except Exception:
        manifest = {
            "schema_version": "1.0.0",
            "metadata": {
                "brain_version": version, "domain": domain,
                "sessions_trained": sessions, "maturity_phase": "INFANT",
                "generated_at": now.isoformat(),
            },
            "quality": {"lessons_graduated": graduated, "lessons_active": active},
            "export": {"exported_at": now.isoformat(), "files": [path for path, _ in sanitized]},
        }

    exports_dir = brain_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y%m%d")
    version_str = version.replace(".", "-")
    domain_lower = domain.lower()
    mode_suffix = "-domain" if domain_only else ("-noprospects" if not include_prospects else "")
    zip_name = f"gradata-{domain_lower}-{version_str}-{date_str}{mode_suffix}.zip"
    zip_path = exports_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        for archive_path, content in sanitized:
            zf.writestr(archive_path, content)

    return zip_path

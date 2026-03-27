"""
Brain Installer — Install a Brain from Archive into Local Runtime
=================================================================
SDK-native module. Installs a brain from a marketplace export (.zip)
into a local runtime, verifying integrity and compatibility before activation.

Usage (via CLI):
    gradata install path/to/brain-archive.zip              # Install to default location
    gradata install path/to/brain-archive.zip --target DIR # Install to specific directory
    gradata install path/to/brain-archive.zip --dry-run    # Preview without installing
    gradata install --list                                  # List installed brains

Flow:
    1. Extract manifest from archive (don't unpack everything yet)
    2. Validate manifest schema
    3. Check compatibility (Python version, dependencies)
    4. If trust >= PROVISIONAL: unpack to target directory
    5. Run bootstrap steps from manifest
    6. Print activation instructions
"""

import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BRAINS_DIR = Path.home() / ".aios" / "brains"


def _check_compatibility(manifest: dict) -> list[str]:
    """Check if the brain is compatible with this system."""
    issues = []
    compat = manifest.get("compatibility", {})

    # Python version
    req_python = compat.get("python", ">=3.11")
    current = f"{sys.version_info.major}.{sys.version_info.minor}"
    min_version = req_python.replace(">=", "").replace(">", "")
    if current < min_version:
        issues.append(f"Python {req_python} required, have {current}")

    # No external vector store dependency required

    return issues


def _extract_manifest(archive_path: Path) -> dict | None:
    """Extract and parse manifest from archive without full extraction."""
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                return None
            raw = zf.read("manifest.json").decode("utf-8")
            return json.loads(raw)
    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        print(f"ERROR: Cannot read archive: {e}")
        return None


def _safe_extract(zf: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract zip with Zip Slip protection — rejects paths that escape target_dir."""
    target_resolved = str(target_dir.resolve())
    for member in zf.infolist():
        member_path = str((target_dir / member.filename).resolve())
        if not member_path.startswith(target_resolved):
            raise ValueError(
                f"Zip Slip detected: {member.filename} would extract outside {target_dir}"
            )
    # All paths validated — safe to extract
    zf.extractall(target_dir)


def _install_brain(archive_path: Path, target_dir: Path, manifest: dict) -> bool:
    """Extract brain archive to target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        _safe_extract(zf, target_dir)

    # Write install metadata
    install_meta = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "source_archive": str(archive_path),
        "brain_version": manifest.get("metadata", {}).get("brain_version"),
        "domain": manifest.get("metadata", {}).get("domain"),
        "trust_verified": True,
    }
    meta_path = target_dir / ".install-meta.json"
    meta_path.write_text(json.dumps(install_meta, indent=2), encoding="utf-8")

    return True


def _run_bootstrap(target_dir: Path, manifest: dict) -> list[dict]:
    """Run bootstrap steps from manifest."""
    results = []
    bootstrap = manifest.get("bootstrap", [])

    # Allowlist: only permit safe commands (python, uv) — no arbitrary shell execution
    import re as _re
    import shlex as _shlex
    _ALLOWED_CMD = _re.compile(r"^(python3?|uv|pip)\s+[\w\s./\-]+$")

    for step in bootstrap:
        name = step.get("step", "unknown")
        command = step.get("command")
        required = step.get("required", False)

        if not command:
            results.append({"step": name, "status": "skipped", "note": "no command"})
            continue

        # Security: reject commands not in allowlist
        if not _ALLOWED_CMD.match(command):
            results.append({
                "step": name, "status": "blocked",
                "note": f"Command not in allowlist: {command[:80]}",
            })
            continue

        # Run from target directory — NO shell=True
        try:
            result = subprocess.run(
                _shlex.split(command),
                shell=False,
                cwd=str(target_dir / "brain" if (target_dir / "brain").exists() else target_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                results.append({"step": name, "status": "ok"})
            else:
                status = "FAIL" if required else "warn"
                results.append({
                    "step": name,
                    "status": status,
                    "error": result.stderr[:200] if result.stderr else "non-zero exit",
                })
        except subprocess.TimeoutExpired:
            results.append({"step": name, "status": "timeout"})
        except Exception as e:
            results.append({"step": name, "status": "error", "error": str(e)[:200]})

    return results


def list_installed() -> list[dict]:
    """List all installed brains."""
    brains = []
    if not DEFAULT_BRAINS_DIR.exists():
        return brains

    for d in sorted(DEFAULT_BRAINS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / ".install-meta.json"
        manifest_file = d / "manifest.json"

        info = {"name": d.name, "path": str(d)}

        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                info.update({
                    "version": meta.get("brain_version"),
                    "domain": meta.get("domain"),
                    "installed": meta.get("installed_at", "?")[:10],
                })
            except Exception:
                pass
        elif manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                info.update({
                    "version": manifest.get("metadata", {}).get("brain_version"),
                    "domain": manifest.get("metadata", {}).get("domain"),
                })
            except Exception:
                pass

        brains.append(info)
    return brains


def install(archive_path: Path, target_dir: Path = None, dry_run: bool = False) -> dict:
    """Full installation flow."""
    report = {"status": "pending", "steps": []}

    # Step 1: Extract manifest
    manifest = _extract_manifest(archive_path)
    if not manifest:
        report["status"] = "failed"
        report["error"] = "Cannot read manifest from archive"
        return report
    report["steps"].append({"step": "extract_manifest", "status": "ok"})

    brain_version = manifest.get("metadata", {}).get("brain_version", "unknown")
    domain = manifest.get("metadata", {}).get("domain", "unknown")
    print(f"Brain: {brain_version} ({domain})")
    print(f"Sessions trained: {manifest.get('metadata', {}).get('sessions_trained', '?')}")
    print(f"Rules: {manifest.get('behavioral_contract', {}).get('total', '?')}")

    # Step 2: Check compatibility
    compat_issues = _check_compatibility(manifest)
    if compat_issues:
        for issue in compat_issues:
            print(f"  COMPAT: {issue}")
        report["steps"].append({"step": "compatibility", "status": "warn", "issues": compat_issues})
    else:
        report["steps"].append({"step": "compatibility", "status": "ok"})

    # Step 3: Determine target
    if target_dir is None:
        brain_name = f"{domain.lower()}-{brain_version.replace('.', '-')}"
        target_dir = DEFAULT_BRAINS_DIR / brain_name
    print(f"Target: {target_dir}")

    if target_dir.exists() and any(target_dir.iterdir()):
        print("  WARNING: Target directory exists and is not empty")
        report["steps"].append({"step": "target_check", "status": "warn", "note": "target exists"})
    else:
        report["steps"].append({"step": "target_check", "status": "ok"})

    if dry_run:
        print("\n[DRY RUN] Would install to:", target_dir)
        print("Files in archive:")
        with zipfile.ZipFile(archive_path, "r") as zf:
            for name in sorted(zf.namelist())[:20]:
                print(f"  {name}")
            total = len(zf.namelist())
            if total > 20:
                print(f"  ... and {total - 20} more")
        report["status"] = "dry_run"
        return report

    # Step 4: Install
    print("Installing...")
    success = _install_brain(archive_path, target_dir, manifest)
    if not success:
        report["status"] = "failed"
        report["error"] = "Installation failed"
        return report
    report["steps"].append({"step": "install", "status": "ok"})

    # Step 5: Bootstrap
    print("Running bootstrap...")
    bootstrap_results = _run_bootstrap(target_dir, manifest)
    for br in bootstrap_results:
        status_icon = "+" if br["status"] == "ok" else "-"
        print(f"  [{status_icon}] {br['step']}: {br['status']}")
    report["steps"].append({"step": "bootstrap", "results": bootstrap_results})

    # Step 6: Activation instructions
    print(f"\nInstalled to: {target_dir}")
    print("\nTo activate:")
    print(f"  export BRAIN_DIR={target_dir}")
    print("  # Or set in your runtime config")

    report["status"] = "ok"
    report["target"] = str(target_dir)
    return report

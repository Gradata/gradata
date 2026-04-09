"""PreToolUse hook: block writes containing secrets (API keys, tokens, private keys)."""
from __future__ import annotations
import re
from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write|Edit|MultiEdit",
    "profile": Profile.STANDARD,
    "timeout": 5000,
    "blocking": True,
}

# Patterns from the JS secret-scan.js
SECRET_PATTERNS = [
    ("openai_key",       re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("aws_access_key",   re.compile(r"AKIA[A-Z0-9]{16}")),
    ("private_key",      re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----")),
    ("github_pat",       re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("jwt_token",        re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}")),
    ("slack_token",      re.compile(r"xox[bpsa]-[a-zA-Z0-9-]{10,}")),
    ("stripe_key",       re.compile(r"[sr]k_live_[a-zA-Z0-9]{20,}")),
    ("stripe_pub",       re.compile(r"pk_live_[a-zA-Z0-9]{20,}")),
    ("sendgrid_key",     re.compile(r"SG\.[a-zA-Z0-9_-]{22,}\.[a-zA-Z0-9_-]{22,}")),
    ("twilio_sid",       re.compile(r"AC[a-f0-9]{32}")),
    ("db_conn_string",   re.compile(r"(?:postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s\"']+", re.I)),
    ("generic_secret",   re.compile(r"(?:password|api_key|token|secret|apikey|api_secret)\s*[=:]\s*[\"']?[^\s\"']{8,}", re.I)),
]


def _scan_content(content: str) -> list[dict]:
    """Scan a string for secret patterns. Returns list of findings."""
    findings = []
    for name, pattern in SECRET_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            findings.extend({"name": name, "preview": "***REDACTED***"} for _ in matches)
    return findings


def main(data: dict) -> dict | None:
    tool_input = data.get("tool_input", {})

    # Collect all content to scan
    contents_to_scan = []
    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if content:
        contents_to_scan.append(content)

    # MultiEdit support: scan each edit's new_string
    for edit in tool_input.get("edits", []):
        edit_content = edit.get("new_string", "")
        if edit_content:
            contents_to_scan.append(edit_content)

    if not contents_to_scan:
        return None

    findings = []
    for text in contents_to_scan:
        findings.extend(_scan_content(text))

    if findings:
        file_path = tool_input.get("file_path", "unknown")
        names = ", ".join(f["name"] for f in findings)
        return {
            "decision": "block",
            "reason": f"SECRET DETECTED: {len(findings)} potential secret(s) in {file_path}: {names}. Move secrets to .env or environment variables.",
        }
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)

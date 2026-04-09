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


def main(data: dict) -> dict | None:
    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None

    tool_input = data.get("tool_input", {})
    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if not content:
        return None

    findings = []
    for name, pattern in SECRET_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            for m in matches:
                preview = m[:8] + "..." if len(m) > 12 else m
                findings.append({"name": name, "preview": preview})

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

"""
Workspace sandbox — validates all file paths stay inside the workspace root.
Also classifies tool risk levels and enforces command allowlists.
"""
import os
import re
from pathlib import Path
from typing import Optional


# ── Risk classification ────────────────────────────────────────────────────────
LOW_RISK_TOOLS = {"list_files", "read_file", "search_files", "get_project_info", "git_status"}
MEDIUM_RISK_TOOLS = {"write_file", "edit_file", "run_command", "run_tests"}
HIGH_RISK_TOOLS = {"delete_file", "run_destructive_command"}


def get_tool_risk(tool_name: str) -> str:
    if tool_name in HIGH_RISK_TOOLS:
        return "high"
    if tool_name in MEDIUM_RISK_TOOLS:
        return "medium"
    return "low"


# ── Path validation ────────────────────────────────────────────────────────────
def validate_path(path: str, workspace_root: str) -> Path:
    """
    Resolve *path* relative to *workspace_root* and ensure the result is
    still inside *workspace_root*.  Raises ValueError on violations.
    """
    workspace = Path(workspace_root).resolve()
    target = (workspace / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    # Reject anything outside the workspace
    try:
        target.relative_to(workspace)
    except ValueError:
        raise ValueError(
            f"Path '{path}' is outside the workspace '{workspace_root}'. "
            "Access denied."
        )
    return target


def is_safe_path(path: str, workspace_root: str) -> bool:
    try:
        validate_path(path, workspace_root)
        return True
    except ValueError:
        return False


# ── Command allowlist ──────────────────────────────────────────────────────────
_ALLOWED_COMMAND_PREFIXES = [
    "python", "py ", "pytest", "pip",
    "node", "npm", "npx",
    "git status", "git log", "git diff", "git branch", "git show",
    "echo", "type", "cat",
    "dir", "ls",
    "java ", "javac ", "mvn ", "gradle ",
    "dotnet ",
    "ruby ", "gem ",
    "cargo ", "rustc ",
    "go ",
    "make ",
]

_BLOCKED_PATTERNS = [
    r"rm\s+-rf",
    r"rmdir\s+/s",
    r"del\s+/[fqs]",
    r"format\s+[a-z]:",
    r"shutdown",
    r"reboot",
    r"reg\s+(add|delete|import)",
    r"net\s+(user|localgroup)",
    r"curl\s+.*\|\s*sh",
    r"wget\s+.*\|\s*sh",
    r"powershell.*-enc",
    r"cmd\s+/c\s+del",
    r"Remove-Item.*-Recurse.*-Force",
    r"mklink\s+/[dj]",         # symlink creation
    r"icacls",
    r"cacls",
    r"attrib\s+.*\+[hs]",
]

_BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


def validate_command(command: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    A command is safe if it matches an allowed prefix AND does not match
    any blocked pattern.
    """
    cmd_lower = command.strip().lower()

    # Check blocked patterns first
    for pattern in _BLOCKED_RE:
        if pattern.search(command):
            return False, f"Command matches blocked pattern: {pattern.pattern}"

    # Check allowed prefixes
    for prefix in _ALLOWED_COMMAND_PREFIXES:
        if cmd_lower.startswith(prefix.lower()):
            return True, "allowed"

    return False, (
        f"Command '{command[:60]}' is not in the allowed list. "
        "Only development-related commands are permitted."
    )


# ── Secret detection ───────────────────────────────────────────────────────────
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),          # OpenAI key
    re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE),          # GitHub PAT
    re.compile(r"(?:password|passwd|secret|api[_-]?key)\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS)


def redact_secrets(text: str) -> str:
    for p in _SECRET_PATTERNS:
        text = p.sub("[REDACTED]", text)
    return text

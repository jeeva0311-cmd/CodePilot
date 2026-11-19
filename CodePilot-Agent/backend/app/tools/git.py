"""
git_status tool — returns actual Git status for the workspace.
"""
import subprocess
from pathlib import Path


def git_status(workspace: str) -> dict:
    root = Path(workspace)

    if not (root / ".git").is_dir():
        return {
            "is_git_repo": False,
            "message": "No .git directory found. This workspace is not a Git repository.",
        }

    def _run(cmd: list[str]) -> tuple[str, int]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return proc.stdout.strip(), proc.returncode
        except Exception as exc:
            return str(exc), -1

    # Branch
    branch_out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_out or "unknown"

    # Status --porcelain
    status_out, _ = _run(["git", "status", "--porcelain"])
    modified = []
    untracked = []
    staged = []

    for line in status_out.splitlines():
        if len(line) < 3:
            continue
        x, y, fname = line[0], line[1], line[3:]
        if x in ("M", "A", "D", "R", "C"):
            staged.append(fname)
        if y == "M":
            modified.append(fname)
        elif y == "?":
            pass  # handled below
        if line.startswith("??"):
            untracked.append(line[3:])

    # Recent log
    log_out, _ = _run(["git", "log", "--oneline", "-5"])
    recent_commits = log_out.splitlines() if log_out else []

    return {
        "is_git_repo": True,
        "branch": branch,
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
        "recent_commits": recent_commits,
        "clean": not status_out.strip(),
    }

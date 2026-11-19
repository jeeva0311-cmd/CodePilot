"""
run_command tool — controlled subprocess execution inside the workspace.
"""
import subprocess
import time
import sys
from pathlib import Path
from app.security.sandbox import validate_command, validate_path
from app.config import settings


def run_command(
    workspace: str,
    command: str,
    working_directory: str = "",
    timeout: int = None,
) -> dict:
    """Execute a development command. Returns stdout, stderr, exit_code, duration."""
    if timeout is None:
        timeout = settings.COMMAND_TIMEOUT

    # Validate command against allowlist / blocklist
    safe, reason = validate_command(command)
    if not safe:
        return {
            "success": False,
            "error": reason,
            "stdout": "",
            "stderr": reason,
            "exit_code": -1,
            "command": command,
            "duration_seconds": 0,
        }

    # Resolve working directory
    cwd = Path(workspace)
    if working_directory:
        try:
            cwd = validate_path(working_directory, workspace)
        except ValueError as exc:
            return {"success": False, "error": str(exc), "stdout": "", "stderr": str(exc), "exit_code": -1, "command": command, "duration_seconds": 0}

    if not cwd.exists():
        return {"success": False, "error": f"Working directory not found: {cwd}", "stdout": "", "stderr": "", "exit_code": -1, "command": command, "duration_seconds": 0}

    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            executable=None,  # use shell
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        stdout = ""
        stderr = f"Command timed out after {timeout} seconds."
        exit_code = -1
    except Exception as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = -1

    duration = round(time.time() - start, 3)

    # Truncate very long outputs
    max_out = 8000
    if len(stdout) > max_out:
        stdout = stdout[:max_out] + "\n… [output truncated] …"
    if len(stderr) > max_out:
        stderr = stderr[:max_out] + "\n… [output truncated] …"

    return {
        "success": exit_code == 0,
        "command": command,
        "working_directory": str(cwd),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "timed_out": timed_out,
    }

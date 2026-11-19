"""
run_tests tool — auto-detects the test framework and executes tests.
"""
from pathlib import Path
from app.tools.terminal import run_command
from app.config import settings


def run_tests(workspace: str, test_path: str = "", framework: str = "auto") -> dict:
    root = Path(workspace)

    if framework == "auto":
        framework = _detect_framework(root)

    if framework == "pytest":
        cmd = f"python -m pytest {test_path} -v --tb=short" if test_path else "python -m pytest -v --tb=short"
    elif framework == "unittest":
        if test_path:
            # Convert path to module notation
            mod = test_path.replace("/", ".").replace("\\", ".").rstrip(".py")
            cmd = f"python -m unittest {mod} -v"
        else:
            cmd = "python -m unittest discover -v"
    elif framework == "jest":
        cmd = f"npx jest {test_path} --no-coverage" if test_path else "npx jest --no-coverage"
    elif framework == "npm_test":
        cmd = "npm test -- --watchAll=false"
    else:
        return {
            "success": False,
            "error": f"Unknown framework '{framework}'. Use pytest, unittest, jest, or auto.",
            "framework": framework,
        }

    result = run_command(workspace, cmd, timeout=settings.COMMAND_TIMEOUT * 2)
    result["framework"] = framework
    result["test_path"] = test_path

    # Parse simple pass/fail summary
    output = result.get("stdout", "") + result.get("stderr", "")
    result["summary"] = _parse_summary(output, framework)

    return result


def _detect_framework(root: Path) -> str:
    """Guess the test framework from project files."""
    # Check for pytest config
    for f in ["pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"]:
        if (root / f).exists():
            try:
                text = (root / f).read_text(encoding="utf-8")
                if "pytest" in text:
                    return "pytest"
            except Exception:
                pass

    # Check requirements.txt
    req = root / "requirements.txt"
    if req.exists():
        try:
            text = req.read_text(encoding="utf-8").lower()
            if "pytest" in text:
                return "pytest"
        except Exception:
            pass

    # Check for test files
    py_tests = list(root.rglob("test_*.py")) + list(root.rglob("*_test.py"))
    if py_tests:
        return "pytest"

    unittest_tests = list(root.rglob("test*.py"))
    if unittest_tests:
        return "unittest"

    # Node
    pkg = root / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "jest" in deps:
                return "jest"
            if "test" in scripts:
                return "npm_test"
        except Exception:
            pass

    return "pytest"  # default


def _parse_summary(output: str, framework: str) -> dict:
    summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    if framework in ("pytest",):
        import re
        m = re.search(r"(\d+) passed", output)
        if m:
            summary["passed"] = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            summary["failed"] = int(m.group(1))
        m = re.search(r"(\d+) error", output)
        if m:
            summary["errors"] = int(m.group(1))
        m = re.search(r"(\d+) skipped", output)
        if m:
            summary["skipped"] = int(m.group(1))
    return summary

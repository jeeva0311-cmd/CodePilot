"""
Filesystem tools: list_files, read_file, write_file, edit_file, get_project_info
"""
import os
import json
import fnmatch
from pathlib import Path
from typing import Optional

from app.security.sandbox import validate_path
from app.config import settings

# Directories to skip when listing
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".tox", "htmlcov", ".eggs",
}


def list_files(workspace: str, directory: str = "", max_depth: int = 3) -> dict:
    base = Path(workspace)
    if directory:
        try:
            base = validate_path(directory, workspace)
        except ValueError as exc:
            return {"error": str(exc)}

    if not base.exists():
        return {"error": f"Directory not found: {directory or workspace}"}

    tree = _build_tree(Path(workspace), base, 0, max_depth)
    return {
        "workspace": workspace,
        "directory": directory or "/",
        "tree": tree,
        "total_shown": _count(tree),
    }


def _build_tree(root: Path, current: Path, depth: int, max_depth: int) -> list:
    if depth > max_depth:
        return [{"name": "…", "type": "truncated"}]
    items = []
    try:
        entries = sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return []
    for entry in entries:
        if entry.name in _SKIP_DIRS or (entry.name.startswith(".") and entry.name != ".env.example"):
            continue
        try:
            rel = str(entry.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        if entry.is_dir():
            children = _build_tree(root, entry, depth + 1, max_depth)
            items.append({"name": entry.name, "path": rel, "type": "directory", "children": children})
        else:
            items.append({"name": entry.name, "path": rel, "type": "file", "size": entry.stat().st_size})
    return items


def _count(tree: list) -> int:
    total = 0
    for item in tree:
        if item.get("type") == "file":
            total += 1
        elif item.get("type") == "directory":
            total += _count(item.get("children", []))
    return total


def read_file(workspace: str, path: str) -> dict:
    try:
        full = validate_path(path, workspace)
    except ValueError as exc:
        return {"error": str(exc)}

    if not full.exists():
        return {"error": f"File not found: {path}"}
    if not full.is_file():
        return {"error": f"Not a file: {path}"}

    size = full.stat().st_size
    if size > settings.MAX_FILE_SIZE_BYTES:
        return {"error": f"File too large ({size} bytes). Max {settings.MAX_FILE_SIZE_BYTES} bytes."}

    try:
        content = full.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"error": f"Cannot read file: {exc}"}

    lines = content.splitlines()
    return {
        "path": path,
        "content": content,
        "lines": len(lines),
        "size_bytes": size,
        "encoding": "utf-8",
    }


def write_file(workspace: str, path: str, content: str) -> dict:
    try:
        full = validate_path(path, workspace)
    except ValueError as exc:
        return {"error": str(exc), "success": False}

    existed = full.exists()
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    except Exception as exc:
        return {"error": f"Cannot write file: {exc}", "success": False}

    return {
        "success": True,
        "path": path,
        "action": "modified" if existed else "created",
        "size_bytes": full.stat().st_size,
        "lines": content.count("\n") + 1,
    }


def edit_file(workspace: str, path: str, old_string: str, new_string: str) -> dict:
    try:
        full = validate_path(path, workspace)
    except ValueError as exc:
        return {"error": str(exc), "success": False}

    if not full.exists():
        return {"error": f"File not found: {path}", "success": False}

    try:
        content = full.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"error": f"Cannot read file: {exc}", "success": False}

    if old_string not in content:
        # Try a more lenient match by normalizing line endings
        normalized = content.replace("\r\n", "\n")
        old_normalized = old_string.replace("\r\n", "\n")
        if old_normalized not in normalized:
            return {
                "error": f"The string to replace was not found in '{path}'. "
                         "Make sure old_string matches the file content exactly, "
                         "including indentation and whitespace.",
                "success": False,
            }
        content = normalized.replace(old_normalized, new_string, 1)
    else:
        content = content.replace(old_string, new_string, 1)

    try:
        full.write_text(content, encoding="utf-8")
    except Exception as exc:
        return {"error": f"Cannot write file: {exc}", "success": False}

    return {
        "success": True,
        "path": path,
        "action": "edited",
        "lines": content.count("\n") + 1,
    }


def get_project_info(workspace: str) -> dict:
    root = Path(workspace)
    info: dict = {
        "workspace": workspace,
        "name": root.name,
        "languages": [],
        "frameworks": [],
        "project_type": "unknown",
        "main_files": [],
        "dependency_files": [],
        "test_directories": [],
        "readme": None,
        "git_repo": False,
        "structure_summary": [],
    }

    # --- Detect languages by extension
    ext_counts: dict[str, int] = {}
    for f in root.rglob("*"):
        if f.is_file() and not any(part in _SKIP_DIRS for part in f.parts):
            ext = f.suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "JavaScript (React)", ".tsx": "TypeScript (React)",
        ".java": "Java", ".cs": "C#", ".go": "Go", ".rs": "Rust",
        ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
        ".cpp": "C++", ".c": "C", ".html": "HTML", ".css": "CSS",
    }
    detected = sorted(ext_counts.items(), key=lambda x: -x[1])
    info["languages"] = [lang_map.get(ext, ext) for ext, _ in detected[:5] if ext in lang_map]

    # --- Detect project type and frameworks
    checks = {
        "requirements.txt": ("Python", "pip"),
        "pyproject.toml": ("Python", "poetry/pyproject"),
        "setup.py": ("Python", "setuptools"),
        "package.json": ("JavaScript/Node", "npm"),
        "Cargo.toml": ("Rust", "cargo"),
        "go.mod": ("Go", "go modules"),
        "pom.xml": ("Java", "Maven"),
        "build.gradle": ("Java/Kotlin", "Gradle"),
        "composer.json": ("PHP", "composer"),
        "Gemfile": ("Ruby", "bundler"),
    }
    for fname, (ptype, fw) in checks.items():
        if (root / fname).exists():
            info["project_type"] = ptype
            info["dependency_files"].append(fname)
            if fw not in info["frameworks"]:
                info["frameworks"].append(fw)

    # --- FastAPI / Flask / Django / React etc.
    _detect_frameworks(root, info)

    # --- Main entry files
    for candidate in ["main.py", "app.py", "server.py", "index.py", "run.py",
                      "index.js", "index.ts", "app.js", "server.js",
                      "Main.java", "Program.cs", "main.go"]:
        if (root / candidate).exists():
            info["main_files"].append(candidate)

    # --- README
    for rname in ["README.md", "README.txt", "README.rst", "readme.md"]:
        if (root / rname).exists():
            info["readme"] = rname
            break

    # --- Test directories
    for tdir in ["tests", "test", "__tests__", "spec", "specs"]:
        if (root / tdir).is_dir():
            info["test_directories"].append(tdir)

    # --- Git
    info["git_repo"] = (root / ".git").is_dir()

    # --- Top-level structure summary (dirs + key files)
    top = []
    try:
        for entry in sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            top.append(f"{'[dir] ' if entry.is_dir() else '[file]'} {entry.name}")
    except Exception:
        pass
    info["structure_summary"] = top[:30]

    return info


def _detect_frameworks(root: Path, info: dict):
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for fw in ["react", "vue", "angular", "svelte", "next", "nuxt", "express", "fastify", "koa"]:
                if fw in deps and fw not in info["frameworks"]:
                    info["frameworks"].append(fw.capitalize())
        except Exception:
            pass

    req = root / "requirements.txt"
    if req.exists():
        try:
            text = req.read_text(encoding="utf-8").lower()
            for fw in ["fastapi", "flask", "django", "tornado", "starlette", "aiohttp", "pytest", "sqlalchemy"]:
                if fw in text and fw not in info["frameworks"]:
                    info["frameworks"].append(fw.capitalize())
        except Exception:
            pass

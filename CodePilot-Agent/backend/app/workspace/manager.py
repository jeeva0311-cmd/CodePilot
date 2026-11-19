"""
Workspace manager — holds the currently selected workspace path
and provides helpers for inspecting it.
"""
import os
import json
from pathlib import Path
from app.config import settings


class WorkspaceManager:
    def __init__(self):
        self._path: str = settings.DEFAULT_WORKSPACE

    @property
    def path(self) -> str:
        return self._path

    def set_path(self, new_path: str) -> dict:
        p = Path(new_path)
        if not p.exists():
            raise ValueError(f"Path does not exist: {new_path}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {new_path}")
        self._path = str(p.resolve())
        return {"success": True, "workspace": self._path}

    def get_info(self) -> dict:
        p = Path(self._path)
        info = {
            "path": self._path,
            "name": p.name,
            "exists": p.exists(),
        }
        if p.exists():
            info["file_count"] = sum(1 for _ in p.rglob("*") if _.is_file())
            info["dir_count"] = sum(1 for _ in p.rglob("*") if _.is_dir())
        return info

    def list_files(self, relative_dir: str = "", max_depth: int = 4) -> list:
        """Return a nested tree structure of the workspace."""
        base = Path(self._path)
        if relative_dir:
            base = base / relative_dir
        base = base.resolve()
        return _build_tree(base, base, 0, max_depth)


_EXCLUDED_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".mypy_cache", ".pytest_cache",
    "*.egg-info", ".tox", "htmlcov",
}


def _build_tree(root: Path, current: Path, depth: int, max_depth: int) -> list:
    if depth > max_depth:
        return []
    items = []
    try:
        entries = sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return []
    for entry in entries:
        if entry.name in _EXCLUDED_DIRS or entry.name.startswith("."):
            continue
        rel = str(entry.relative_to(root)).replace("\\", "/")
        if entry.is_dir():
            children = _build_tree(root, entry, depth + 1, max_depth)
            items.append({"name": entry.name, "path": rel, "type": "directory", "children": children})
        else:
            items.append({"name": entry.name, "path": rel, "type": "file", "size": entry.stat().st_size})
    return items


# Singleton
workspace_manager = WorkspaceManager()

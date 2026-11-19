"""
search_files tool — text/regex search across workspace files.
"""
import re
import fnmatch
from pathlib import Path
from app.security.sandbox import validate_path

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".mypy_cache", ".pytest_cache",
}
_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".md", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".sh", ".bat", ".java", ".cs", ".go", ".rs", ".rb", ".php",
    ".xml", ".sql", ".graphql", ".proto", ".tf",
}


def search_files(
    workspace: str,
    query: str,
    directory: str = "",
    file_pattern: str = "",
    case_sensitive: bool = False,
    max_results: int = 50,
) -> dict:
    if not query:
        return {"error": "query must not be empty"}

    base = Path(workspace)
    if directory:
        try:
            base = validate_path(directory, workspace)
        except ValueError as exc:
            return {"error": str(exc)}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as exc:
        # Fall back to literal search
        pattern = re.compile(re.escape(query), flags)

    results = []
    files_searched = 0

    for path in _iter_files(base):
        # Skip binary-looking files
        if path.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        # Apply file_pattern filter
        if file_pattern and not fnmatch.fnmatch(path.name, file_pattern):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        files_searched += 1
        for i, line in enumerate(content.splitlines(), 1):
            if pattern.search(line):
                try:
                    rel = str(path.relative_to(Path(workspace))).replace("\\", "/")
                except ValueError:
                    rel = str(path)
                results.append({
                    "file": rel,
                    "line": i,
                    "content": line.strip()[:200],
                })
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    return {
        "query": query,
        "results": results,
        "total_matches": len(results),
        "files_searched": files_searched,
        "truncated": len(results) >= max_results,
    }


def _iter_files(directory: Path):
    try:
        for entry in sorted(directory.iterdir(), key=lambda e: e.name):
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            if entry.is_dir():
                yield from _iter_files(entry)
            elif entry.is_file():
                yield entry
    except PermissionError:
        pass

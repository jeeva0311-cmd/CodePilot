"""File reading endpoint (for the file explorer preview)."""
from fastapi import APIRouter, HTTPException, Query
from app.workspace import workspace_manager
from app.security import validate_path
from app.config import settings

router = APIRouter()


@router.get("/files/read")
def read_file(path: str = Query(..., description="Path relative to workspace")):
    try:
        full_path = validate_path(path, workspace_manager.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not full_path.exists():
        raise HTTPException(404, f"File not found: {path}")
    if not full_path.is_file():
        raise HTTPException(400, f"Not a file: {path}")

    size = full_path.stat().st_size
    if size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(400, f"File too large ({size} bytes). Max {settings.MAX_FILE_SIZE_BYTES} bytes.")

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(500, f"Could not read file: {exc}")

    return {
        "path": path,
        "content": content,
        "size": size,
        "lines": content.count("\n") + 1,
    }

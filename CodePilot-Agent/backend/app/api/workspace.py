"""Workspace selection and file explorer endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.workspace import workspace_manager

router = APIRouter()


class WorkspaceSetRequest(BaseModel):
    path: str


@router.get("/workspace")
def get_workspace():
    return workspace_manager.get_info()


@router.post("/workspace")
def set_workspace(body: WorkspaceSetRequest):
    try:
        return workspace_manager.set_path(body.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/workspace/files")
def list_workspace_files(dir: str = "", depth: int = 4):
    try:
        return {"files": workspace_manager.list_files(dir, min(depth, 6))}
    except Exception as exc:
        raise HTTPException(400, str(exc))

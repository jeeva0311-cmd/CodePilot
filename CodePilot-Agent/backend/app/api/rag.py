"""RAG endpoints — index workspace, query, stats, clear."""
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.rag.store import rag_store
from app.workspace import workspace_manager
from app.config import settings

router = APIRouter()


class IndexRequest(BaseModel):
    workspace_path: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    workspace_path: Optional[str] = None
    top_k: int = 5


@router.post("/rag/index")
def index_workspace(body: IndexRequest):
    """Trigger async workspace indexing. Returns immediately; runs in background."""
    if not settings.RAG_ENABLED:
        return {"status": "disabled", "message": "RAG is disabled in settings"}

    ws = body.workspace_path or workspace_manager.path
    # Run in background thread so it doesn't block the HTTP response
    t = threading.Thread(target=_do_index, args=(ws,), daemon=True)
    t.start()
    return {"status": "indexing_started", "workspace": ws}


def _do_index(ws: str):
    try:
        result = rag_store.index_workspace(ws)
        import logging
        logging.getLogger("codepilot.rag").info(f"Index complete: {result}")
    except Exception as exc:
        import logging
        logging.getLogger("codepilot.rag").error(f"Index failed: {exc}")


@router.post("/rag/query")
def query_rag(body: QueryRequest):
    """Semantic search over indexed workspace."""
    if not settings.RAG_ENABLED:
        return {"results": [], "message": "RAG disabled"}
    ws = body.workspace_path or workspace_manager.path
    results = rag_store.query(ws, body.query, top_k=body.top_k)
    return {"results": results, "count": len(results), "workspace": ws}


@router.get("/rag/stats")
def rag_stats(workspace_path: Optional[str] = None):
    ws = workspace_path or workspace_manager.path
    return rag_store.get_collection_stats(ws)


@router.delete("/rag/index")
def clear_index(workspace_path: Optional[str] = None):
    ws = workspace_path or workspace_manager.path
    return rag_store.clear_workspace_index(ws)

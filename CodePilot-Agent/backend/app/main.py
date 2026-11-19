"""
CodePilot Agent — FastAPI application entry point.
"""
import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("codepilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CodePilot Agent …")
    init_db()
    logger.info("Database initialised.")
    # Kick off workspace RAG indexing in the background (non-blocking)
    if settings.RAG_ENABLED:
        threading.Thread(target=_background_index, daemon=True).start()
    yield
    logger.info("Shutting down CodePilot Agent.")


def _background_index():
    try:
        from app.rag.store import rag_store
        result = rag_store.index_workspace(settings.DEFAULT_WORKSPACE)
        logger.info(f"Background RAG index: {result}")
    except Exception as exc:
        logger.warning(f"Background RAG index skipped: {exc}")


app = FastAPI(
    title="CodePilot Agent",
    version="1.1.0",
    description="AI Coding Agent with RAG",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routers ───────────────────────────────────────────────────────
from app.api import (
    health, conversations, agent, workspace,
    settings as settings_router, files, approvals,
)
from app.api import auth, rag

app.include_router(health.router,          prefix="/api", tags=["health"])
app.include_router(auth.router,            prefix="/api", tags=["auth"])
app.include_router(conversations.router,   prefix="/api", tags=["conversations"])
app.include_router(agent.router,           prefix="/api", tags=["agent"])
app.include_router(workspace.router,       prefix="/api", tags=["workspace"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(files.router,           prefix="/api", tags=["files"])
app.include_router(approvals.router,       prefix="/api", tags=["approvals"])
app.include_router(rag.router,             prefix="/api", tags=["rag"])

# ── Serve frontend ────────────────────────────────────────────────────────────
_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(_FRONTEND / "index.html"))

    @app.get("/login", include_in_schema=False)
    @app.get("/signup", include_in_schema=False)
    @app.get("/about", include_in_schema=False)
    @app.get("/chat", include_in_schema=False)
    async def serve_app():
        return FileResponse(str(_FRONTEND / "index.html"))

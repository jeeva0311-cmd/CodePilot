"""Settings endpoints — get/set configuration, test LLM connection."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os

from app.database import get_db
from app.models import Setting
from app.config import settings as app_settings

router = APIRouter()


class SettingUpdate(BaseModel):
    key: str
    value: str


class ProviderUpdate(BaseModel):
    provider: str        # "groq" | "openai" | "openrouter" | "ollama" | "custom"
    api_key: str
    model: str
    base_url: str = ""


_PROVIDER_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": None,  # use base_url as-is
}

_PROVIDER_MODELS = {
    "groq": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "allam-2-7b"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "openrouter": ["meta-llama/llama-3.3-70b-instruct", "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
    "ollama": ["llama3.2", "mistral", "codellama"],
    "custom": [],
}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return {
        "model": rows.get("model", app_settings.OPENAI_MODEL),
        "max_iterations": rows.get("max_iterations", str(app_settings.MAX_AGENT_ITERATIONS)),
        "command_timeout": rows.get("command_timeout", str(app_settings.COMMAND_TIMEOUT)),
        "require_approval_high": rows.get("require_approval_high", "true"),
        "require_approval_medium": rows.get("require_approval_medium", "false"),
        "api_key_configured": app_settings.api_key_configured,
        "api_base_url": rows.get("api_base_url", app_settings.OPENAI_BASE_URL or "(default)"),
        "provider": rows.get("provider", _detect_provider(app_settings.OPENAI_BASE_URL)),
        "rag_enabled": str(app_settings.RAG_ENABLED).lower(),
        "rag_top_k": str(app_settings.RAG_TOP_K),
        "provider_models": _PROVIDER_MODELS,
    }


def _detect_provider(base_url: str) -> str:
    if not base_url:
        return "openai"
    if "groq.com" in base_url:
        return "groq"
    if "openrouter.ai" in base_url:
        return "openrouter"
    if "localhost:11434" in base_url:
        return "ollama"
    return "custom"


@router.post("/settings")
def update_setting(body: SettingUpdate, db: Session = Depends(get_db)):
    # Never store raw API keys in the DB via this generic endpoint
    if body.key.lower() in ("api_key", "openai_api_key", "secret"):
        return {"error": "API keys must be set via /api/settings/provider or the .env file."}

    row = db.query(Setting).filter(Setting.key == body.key).first()
    if row:
        row.value = body.value
        row.updated_at = datetime.utcnow()
    else:
        row = Setting(key=body.key, value=body.value)
        db.add(row)
    db.commit()

    # Apply live if it's model/url
    if body.key == "model":
        app_settings.OPENAI_MODEL = body.value
        app_settings.reset_llm_client()
    elif body.key == "api_base_url":
        app_settings.OPENAI_BASE_URL = body.value
        app_settings.reset_llm_client()

    return {"success": True, "key": body.key}


@router.post("/settings/provider")
def update_provider(body: ProviderUpdate, db: Session = Depends(get_db)):
    """Update LLM provider + API key. Resets the live LLM client."""
    if body.provider not in _PROVIDER_URLS and body.provider != "custom":
        return {"error": f"Unknown provider: {body.provider}"}

    base_url = _PROVIDER_URLS.get(body.provider, body.base_url)
    if body.provider == "custom":
        base_url = body.base_url

    # Update in-memory settings
    if body.api_key:
        app_settings.OPENAI_API_KEY = body.api_key
    app_settings.OPENAI_BASE_URL = base_url or ""
    app_settings.OPENAI_MODEL = body.model
    app_settings.reset_llm_client()

    # Persist non-sensitive parts to DB
    _upsert(db, "provider", body.provider)
    _upsert(db, "model", body.model)
    _upsert(db, "api_base_url", base_url or "(default)")

    return {
        "success": True,
        "provider": body.provider,
        "model": body.model,
        "base_url": base_url or "(default)",
        "api_key_configured": bool(body.api_key),
    }


def _upsert(db, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


@router.get("/settings/db-info")
def db_info():
    db_path = app_settings.DATABASE_PATH
    size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    return {"path": db_path, "size_bytes": size, "size_kb": round(size / 1024, 2)}

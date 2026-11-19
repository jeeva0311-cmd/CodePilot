"""Health check and API status endpoints."""
from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "api_key_configured": settings.api_key_configured,
        "model": settings.OPENAI_MODEL,
    }


@router.get("/health/llm")
async def test_llm_connection():
    """Quick LLM connectivity test — sends a minimal request."""
    if not settings.api_key_configured:
        return {"status": "not_configured", "message": "OPENAI_API_KEY is not set."}
    try:
        from app.agent.llm_client import llm_client
        ok = await llm_client.test_connection()
        if ok:
            return {"status": "connected", "model": settings.OPENAI_MODEL, "provider": settings.OPENAI_BASE_URL or "openai"}
        return {"status": "error", "message": "LLM returned unexpected response."}
    except (ValueError, ConnectionError) as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"Unexpected error: {exc}"}

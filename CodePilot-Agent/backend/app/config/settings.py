"""
Application configuration — reads from environment / .env file.
Never put secrets directly in this file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env", override=False)


class Settings:
    # ── LLM ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

    # ── Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET: str = os.getenv("JWT_SECRET", "codepilot-change-me")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

    # ── Agent ─────────────────────────────────────────────────────────────
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "12"))
    COMMAND_TIMEOUT: int = int(os.getenv("COMMAND_TIMEOUT", "30"))
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(1024 * 512)))

    # ── RAG ───────────────────────────────────────────────────────────────
    RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "true").lower() == "true"
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "800"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))

    # ── Server ────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        str(_ROOT / "backend" / "codepilot.db"),
    )

    # ── Workspace ─────────────────────────────────────────────────────────
    DEFAULT_WORKSPACE: str = os.getenv("DEFAULT_WORKSPACE", str(_ROOT))

    # ── Security ──────────────────────────────────────────────────────────
    REQUIRE_APPROVAL_FOR_HIGH_RISK: bool = (
        os.getenv("REQUIRE_APPROVAL_FOR_HIGH_RISK", "true").lower() == "true"
    )
    REQUIRE_APPROVAL_FOR_MEDIUM_RISK: bool = (
        os.getenv("REQUIRE_APPROVAL_FOR_MEDIUM_RISK", "false").lower() == "true"
    )

    CORS_ORIGINS: list[str] = ["*"]

    @property
    def api_key_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY != "your-api-key-here")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.DATABASE_PATH}"

    def reload_from_db(self, db):
        """Pull overrides from the settings table so UI changes take effect live."""
        try:
            from app.models.setting import Setting
            rows = {r.key: r.value for r in db.query(Setting).all()}
            if "model" in rows:
                self.OPENAI_MODEL = rows["model"]
            if "api_base_url" in rows and rows["api_base_url"] not in ("", "(default)"):
                self.OPENAI_BASE_URL = rows["api_base_url"]
            if "api_key" in rows and rows["api_key"]:
                self.OPENAI_API_KEY = rows["api_key"]
            if "max_iterations" in rows:
                self.MAX_AGENT_ITERATIONS = int(rows["max_iterations"])
            if "command_timeout" in rows:
                self.COMMAND_TIMEOUT = int(rows["command_timeout"])
        except Exception:
            pass

    def reset_llm_client(self):
        """Force the LLM client to reconnect with new credentials."""
        try:
            from app.agent.llm_client import llm_client
            llm_client._client = None
        except Exception:
            pass


settings = Settings()

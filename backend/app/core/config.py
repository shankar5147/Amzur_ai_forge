from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend root directory regardless of cwd
_backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(_backend_dir / ".env")


def _parse_origins(value: str) -> tuple[str, ...]:
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return tuple(origins)


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # LiteLLM proxy settings
    litellm_proxy_url: str = os.getenv("LITELLM_PROXY_URL", "http://litellm.amzur.com:4000")
    litellm_virtual_key: str = os.getenv("LITELLM_VIRTUAL_KEY", "")
    litellm_user_id: str = os.getenv("LITELLM_USER_ID", "")
    litellm_model: str = os.getenv("LITELLM_MODEL", "gemini-1.5-flash")
    litellm_department: str = os.getenv("LITELLM_DEPARTMENT", "AIForge")
    litellm_environment: str = os.getenv("LITELLM_ENVIRONMENT", "testing")

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_forge_chatbot")

    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "change-this-secret-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # Google OAuth
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # Google Sheets API (service-account credentials for private sheets)
    google_sheets_credentials_file: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")

    # CORS
    frontend_origin_regex: str = os.getenv(
        "FRONTEND_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    )
    frontend_origins: tuple[str, ...] = _parse_origins(
        os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        )
    )

    # Attachments
    upload_dir: str = os.getenv("UPLOAD_DIR", str(_backend_dir / "uploads"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))  # Per-file limit
    max_total_upload_bytes: int = int(os.getenv("MAX_TOTAL_UPLOAD_BYTES", str(100 * 1024 * 1024)))  # Total per request
    max_files_per_upload: int = int(os.getenv("MAX_FILES_PER_UPLOAD", "20"))
    max_attachment_context_items: int = int(os.getenv("MAX_ATTACHMENT_CONTEXT_ITEMS", "5"))

    # RAG + embeddings
    rag_enabled: bool = _parse_bool(os.getenv("RAG_ENABLED", "true"), default=True)
    rag_embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "1200"))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "6"))
    rag_max_chunks_per_attachment: int = int(os.getenv("RAG_MAX_CHUNKS_PER_ATTACHMENT", "200"))
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", str(_backend_dir / ".chroma_data"))

    # AI image generation
    imagen_model: str = os.getenv("IMAGEN_MODEL", "gemini/imagen-4.0-fast-generate-001")
    max_image_prompt_chars: int = int(os.getenv("MAX_IMAGE_PROMPT_CHARS", "1000"))
    image_generation_rate_limit_count: int = int(os.getenv("IMAGE_GENERATION_RATE_LIMIT_COUNT", "5"))
    image_generation_rate_limit_window_seconds: int = int(os.getenv("IMAGE_GENERATION_RATE_LIMIT_WINDOW_SECONDS", "60"))


settings = Settings()

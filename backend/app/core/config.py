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


settings = Settings()

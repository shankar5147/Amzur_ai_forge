from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.attachments import router as attachments_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.threads import router as thread_router
from app.core.config import settings
from app.core.database import engine
from app.models.db_models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_ready = False
    app.state.db_error = None

    # Create tables on startup (use Alembic in production).
    # Do not crash service startup if DB is temporarily unreachable.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.db_ready = True
    except Exception as exc:
        app.state.db_error = str(exc)
        logger.warning(
            "Database startup check failed. Service will run in degraded mode. Cause: %s",
            exc,
        )

    yield
    await engine.dispose()


app = FastAPI(title="AI Forge Chatbot API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_origin_regex=settings.frontend_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(thread_router)
app.include_router(attachments_router)

upload_dir = Path(settings.upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

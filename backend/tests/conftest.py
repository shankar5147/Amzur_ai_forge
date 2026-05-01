"""
Shared test fixtures for the backend test suite.
Uses SQLite in-memory DB for isolation and speed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.models.db_models import Base, User
from app.services.auth_service import AuthService

# In-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create tables and provide a clean session per test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionFactory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def app(db_session: AsyncSession):
    """FastAPI app with overridden DB dependency."""
    from app.main import app as _app

    async def _override_get_db():
        yield db_session

    _app.dependency_overrides[get_db] = _override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client for testing endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the DB."""
    user = User(
        id=uuid.uuid4(),
        email="test@amzur.com",
        hashed_password=AuthService.hash_password("TestPass123!"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Get auth headers for the test user."""
    token = AuthService.create_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}

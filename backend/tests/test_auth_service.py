"""Tests for auth service layer."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import User
from app.services.auth_service import AuthError, AuthService


class TestHashPassword:
    def test_returns_hashed_string(self):
        hashed = AuthService.hash_password("mypassword")
        assert hashed != "mypassword"
        assert hashed.startswith("$2b$")

    def test_different_salts_produce_different_hashes(self):
        h1 = AuthService.hash_password("same")
        h2 = AuthService.hash_password("same")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        hashed = AuthService.hash_password("correct")
        assert AuthService.verify_password("correct", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = AuthService.hash_password("correct")
        assert AuthService.verify_password("wrong", hashed) is False


class TestCreateAndDecodeToken:
    def test_create_token_returns_string(self):
        uid = uuid.uuid4()
        token = AuthService.create_token(uid)
        assert isinstance(token, str)
        assert len(token) > 10

    def test_decode_token_returns_correct_sub(self):
        uid = uuid.uuid4()
        token = AuthService.create_token(uid)
        payload = AuthService.decode_token(token)
        assert payload["sub"] == str(uid)

    def test_decode_invalid_token_raises_auth_error(self):
        with pytest.raises(AuthError, match="Invalid token"):
            AuthService.decode_token("invalid.token.here")

    def test_decode_expired_token_raises_auth_error(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from app.core.config import settings

        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
        }
        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthError, match="expired"):
            AuthService.decode_token(token)


class TestSignup:
    @pytest.mark.asyncio
    async def test_signup_creates_user(self, db_session: AsyncSession):
        service = AuthService(db_session)
        user = await service.signup("new@amzur.com", "StrongPass1!", "New User")
        assert user.email == "new@amzur.com"
        assert user.full_name == "New User"
        assert user.hashed_password is not None

    @pytest.mark.asyncio
    async def test_signup_duplicate_email_raises(self, db_session: AsyncSession, test_user: User):
        service = AuthService(db_session)
        with pytest.raises(AuthError, match="already exists"):
            await service.signup(test_user.email, "AnotherPass1!", "Another User")


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, db_session: AsyncSession, test_user: User):
        service = AuthService(db_session)
        user = await service.login("test@amzur.com", "TestPass123!")
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session: AsyncSession, test_user: User):
        service = AuthService(db_session)
        with pytest.raises(AuthError, match="Invalid email or password"):
            await service.login("test@amzur.com", "WrongPassword!")

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, db_session: AsyncSession):
        service = AuthService(db_session)
        with pytest.raises(AuthError, match="Invalid email or password"):
            await service.login("nobody@amzur.com", "Anything123!")


class TestGoogleLogin:
    @pytest.mark.asyncio
    async def test_google_login_creates_new_user(self, db_session: AsyncSession):
        service = AuthService(db_session)
        user = await service.google_login("google123", "google@amzur.com", "Google User", "https://img.url/pic.jpg")
        assert user.email == "google@amzur.com"
        assert user.google_id == "google123"
        assert user.avatar_url == "https://img.url/pic.jpg"
        assert user.hashed_password is None

    @pytest.mark.asyncio
    async def test_google_login_links_existing_email(self, db_session: AsyncSession, test_user: User):
        service = AuthService(db_session)
        user = await service.google_login("google456", test_user.email, "Test User", "https://img.url/pic.jpg")
        assert user.id == test_user.id
        assert user.google_id == "google456"

    @pytest.mark.asyncio
    async def test_google_login_existing_google_id(self, db_session: AsyncSession):
        service = AuthService(db_session)
        # First login creates user
        user1 = await service.google_login("gid789", "g@amzur.com", "G User")
        # Second login finds by google_id
        user2 = await service.google_login("gid789", "g@amzur.com", "G User")
        assert user1.id == user2.id

    @pytest.mark.asyncio
    async def test_google_login_updates_avatar(self, db_session: AsyncSession):
        service = AuthService(db_session)
        user = await service.google_login("gid_av", "av@amzur.com", "Av User", "https://old.jpg")
        user2 = await service.google_login("gid_av", "av@amzur.com", "Av User", "https://new.jpg")
        assert user2.avatar_url == "https://new.jpg"

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.db_models import User


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @staticmethod
    def create_token(user_id: uuid.UUID) -> str:
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired.")
        except jwt.InvalidTokenError:
            raise AuthError("Invalid token.")

    async def signup(self, email: str, password: str, full_name: str) -> User:
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        if result.scalar_one_or_none():
            raise AuthError("A user with this email already exists.")

        user = User(
            email=email,
            hashed_password=self.hash_password(password),
            full_name=full_name,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def login(self, email: str, password: str) -> User:
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password or not self.verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password.")

        return user

    async def google_login(self, google_id: str, email: str, full_name: str, avatar_url: str | None = None) -> User:
        """Handle Google OAuth login. Creates user if not exists, links if exists by email."""
        # Check if user exists by google_id
        stmt = select(User).where(User.google_id == google_id)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update avatar if changed
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
                await self._db.commit()
                await self._db.refresh(user)
            return user

        # Check if user exists by email (link Google account)
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.google_id = google_id
            if avatar_url:
                user.avatar_url = avatar_url
            await self._db.commit()
            await self._db.refresh(user)
            return user

        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            google_id=google_id,
            avatar_url=avatar_url,
            hashed_password=None,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

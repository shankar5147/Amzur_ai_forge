from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Thread


class ThreadService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_thread(self, user_id: uuid.UUID, name: str = "New Chat") -> Thread:
        thread = Thread(user_id=user_id, name=name)
        self._db.add(thread)
        await self._db.commit()
        await self._db.refresh(thread)
        return thread

    async def get_threads(self, user_id: uuid.UUID) -> list[Thread]:
        stmt = (
            select(Thread)
            .where(Thread.user_id == user_id)
            .order_by(Thread.updated_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> Thread | None:
        stmt = select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID, name: str) -> Thread | None:
        thread = await self.get_thread(thread_id, user_id)
        if not thread:
            return None
        thread.name = name
        await self._db.commit()
        await self._db.refresh(thread)
        return thread

    async def delete_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        thread = await self.get_thread(thread_id, user_id)
        if not thread:
            return False
        await self._db.delete(thread)
        await self._db.commit()
        return True

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Message


class MessageService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_message(self, thread_id: uuid.UUID, user_id: uuid.UUID, role: str, content: str) -> Message:
        message = Message(thread_id=thread_id, user_id=user_id, role=role, content=content)
        self._db.add(message)
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def get_history(self, thread_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_history(self, thread_id: uuid.UUID, limit: int = 5) -> list[Message]:
        """Fetch the last N messages for a thread in chronological order."""
        # Subquery: get last N messages ordered desc, then re-order asc
        stmt = (
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        messages = list(result.scalars().all())
        # Return in chronological order
        messages.reverse()
        return messages

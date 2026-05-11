from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import Attachment, Message, Thread
from app.services.attachment_rag_service import AttachmentRAGService
from app.services.file_storage_service import FileStorageService


class AttachmentService:
    def __init__(self, db: AsyncSession, storage: FileStorageService | None = None) -> None:
        self._db = db
        self._storage = storage or FileStorageService()

    async def upload_files_for_thread(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        files: list,
    ) -> list[Attachment]:
        thread = await self._get_user_thread(thread_id, user_id)
        if thread is None:
            return []

        saved: list[Attachment] = []
        for upload in files:
            stored = await self._storage.save_upload(thread_id=thread_id, upload=upload)
            attachment = Attachment(
                thread_id=thread_id,
                file_name=stored.file_name,
                mime_type=stored.mime_type,
                file_path=stored.file_path,
            )
            self._db.add(attachment)
            saved.append(attachment)

        await self._db.commit()
        for attachment in saved:
            await self._db.refresh(attachment)

        # Best-effort indexing for retrieval; upload should still succeed if indexing fails.
        try:
            rag_service = AttachmentRAGService(self._db, storage=self._storage)
            await rag_service.retrieve_context_blocks(saved, query="")
        except Exception:
            pass

        return saved

    async def list_thread_attachments(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> list[Attachment]:
        stmt = (
            select(Attachment)
            .join(Thread, Thread.id == Attachment.thread_id)
            .where(Attachment.thread_id == thread_id, Thread.user_id == user_id)
            .order_by(Attachment.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_attachment_for_user(self, attachment_id: uuid.UUID, user_id: uuid.UUID) -> Attachment | None:
        stmt = (
            select(Attachment)
            .join(Thread, Thread.id == Attachment.thread_id)
            .where(Attachment.id == attachment_id, Thread.user_id == user_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_attachments_by_ids(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
    ) -> list[Attachment]:
        if not attachment_ids:
            return []

        stmt = (
            select(Attachment)
            .join(Thread, Thread.id == Attachment.thread_id)
            .where(
                Attachment.id.in_(attachment_ids),
                Attachment.thread_id == thread_id,
                Thread.user_id == user_id,
            )
            .order_by(Attachment.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def attach_to_message(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
    ) -> None:
        if not attachment_ids:
            return

        attachments = await self.get_attachments_by_ids(thread_id, user_id, attachment_ids)
        for attachment in attachments:
            attachment.message_id = message_id

        await self._db.commit()

    async def get_message_with_attachments(self, message_id: uuid.UUID) -> Message | None:
        stmt = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.id == message_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_user_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> Thread | None:
        stmt = select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter

import anyio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.db_models import Attachment, AttachmentChunk
from app.services.chromadb_service import ChromaDBService
from app.services.document_processor_service import DocumentProcessorService
from app.services.embedding_service import EmbeddingService
from app.services.file_storage_service import FileStorageService

logger = logging.getLogger("uvicorn.error")


class AttachmentRAGService:
    def __init__(self, db: AsyncSession, storage: FileStorageService | None = None) -> None:
        self._db = db
        self._storage = storage or FileStorageService()
        self._processor = DocumentProcessorService()
        self._embedder = EmbeddingService()

    async def retrieve_context_blocks(self, attachments: list[Attachment], query: str) -> list[str]:
        if not settings.rag_enabled or not attachments:
            logger.info("[RAG] Skipping retrieval (enabled=%s, attachments=%s)", settings.rag_enabled, len(attachments))
            return []

        logger.info(
            "[RAG] Starting retrieval: attachments=%s, top_k=%s, query='%s'",
            len(attachments),
            settings.rag_top_k,
            query[:120],
        )
        await self._ensure_chunks(attachments)
        attachment_ids = [attachment.id for attachment in attachments]

        # Generate query embedding
        query_embedding = await self._embedder.generate_embedding(query)

        # Query ChromaDB if embedding available
        if query_embedding:
            try:
                results = await ChromaDBService.query_embeddings(
                    query_embedding=query_embedding,
                    n_results=max(1, settings.rag_top_k),
                    where={"attachment_id": {"$in": [str(aid) for aid in attachment_ids]}},
                )
                chunk_ids = [uuid.UUID(cid) for cid in results.get("ids", [])]
                logger.info("[RAG] Chroma returned %s chunk ids", len(chunk_ids))
                if chunk_ids:
                    chunks = await self._get_chunks_by_id(chunk_ids)
                    attachments_by_id = {attachment.id: attachment for attachment in attachments}
                    blocks: list[str] = []
                    for chunk in chunks:
                        attachment = attachments_by_id.get(chunk.attachment_id)
                        source_name = attachment.file_name if attachment else str(chunk.attachment_id)
                        blocks.append(
                            f"[RAG source: {source_name} | chunk {chunk.chunk_index + 1}]\n{chunk.content_chunk}"
                        )
                    logger.info("[RAG] Retrieved %s chunks from Chroma", len(blocks))
                    return blocks
            except Exception:
                # Fall back to lexical search if ChromaDB fails
                logger.exception("[RAG] Chroma query failed, using lexical fallback")
                pass
        else:
            logger.info("[RAG] Query embedding unavailable, using lexical fallback")

        # Fallback: lexical search when embeddings unavailable
        chunks = await self._get_chunks(attachment_ids)
        if not chunks:
            return []

        ranked = self._rank_chunks_lexical(chunks=chunks, query=query)
        if not ranked:
            logger.info("[RAG] Lexical fallback found 0 matches")
            return []

        attachments_by_id = {attachment.id: attachment for attachment in attachments}
        top_n = ranked[: max(1, settings.rag_top_k)]

        blocks: list[str] = []
        for chunk, _score in top_n:
            attachment = attachments_by_id.get(chunk.attachment_id)
            source_name = attachment.file_name if attachment else str(chunk.attachment_id)
            blocks.append(
                f"[RAG source: {source_name} | chunk {chunk.chunk_index + 1}]\n{chunk.content_chunk}"
            )

        logger.info("[RAG] Lexical fallback retrieved %s chunks", len(blocks))
        return blocks

    async def _ensure_chunks(self, attachments: list[Attachment]) -> None:
        existing = await self._chunk_counts([attachment.id for attachment in attachments])

        for attachment in attachments:
            if existing.get(attachment.id, 0) > 0:
                continue

            if not self._is_chunkable(attachment.mime_type):
                continue

            file_path = self._storage.resolve_path(attachment.file_path)
            if not file_path.exists():
                continue

            try:
                content = await anyio.to_thread.run_sync(
                    self._processor.extract_text,
                    file_path,
                    attachment.mime_type,
                    attachment.file_name,
                )
            except Exception:
                continue

            chunks = self._processor.chunk_text(
                content,
                chunk_size=settings.rag_chunk_size,
                overlap=settings.rag_chunk_overlap,
            )
            chunks = chunks[: settings.rag_max_chunks_per_attachment]
            if not chunks:
                continue

            embeddings = await self._embedder.generate_embeddings(chunks)
            embedded_count = sum(1 for item in embeddings if item)
            logger.info(
                "[RAG] Prepared %s chunks for attachment %s (embeddings: %s)",
                len(chunks),
                attachment.id,
                embedded_count,
            )

            # Save chunks to PostgreSQL
            chunk_objects = []
            chunk_ids = []
            for index, chunk in enumerate(chunks):
                chunk_id = uuid.uuid4()
                chunk_ids.append(str(chunk_id))
                chunk_obj = AttachmentChunk(
                    id=chunk_id,
                    attachment_id=attachment.id,
                    chunk_index=index,
                    content_chunk=chunk,
                )
                chunk_objects.append(chunk_obj)
                self._db.add(chunk_obj)

            await self._db.commit()

            # Add embeddings to ChromaDB
            metadatas = [
                {
                    "attachment_id": str(attachment.id),
                    "chunk_index": index,
                }
                for index in range(len(chunks))
            ]
            await ChromaDBService.add_embeddings(
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )
            logger.info("[RAG] Indexed %s vectors in Chroma for attachment %s", embedded_count, attachment.id)

    async def reindex_attachment(self, attachment: Attachment) -> None:
        await self._db.execute(
            delete(AttachmentChunk).where(AttachmentChunk.attachment_id == attachment.id)
        )
        await self._db.commit()
        await ChromaDBService.delete_by_attachment(attachment.id)
        await self._ensure_chunks([attachment])

    async def _get_chunks(self, attachment_ids: list[uuid.UUID]) -> list[AttachmentChunk]:
        if not attachment_ids:
            return []

        stmt = (
            select(AttachmentChunk)
            .where(AttachmentChunk.attachment_id.in_(attachment_ids))
            .order_by(AttachmentChunk.attachment_id.asc(), AttachmentChunk.chunk_index.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _get_chunks_by_id(self, chunk_ids: list[uuid.UUID]) -> list[AttachmentChunk]:
        if not chunk_ids:
            return []

        stmt = (
            select(AttachmentChunk)
            .where(AttachmentChunk.id.in_(chunk_ids))
            .order_by(AttachmentChunk.chunk_index.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _chunk_counts(self, attachment_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        chunks = await self._get_chunks(attachment_ids)
        counts: dict[uuid.UUID, int] = {}
        for chunk in chunks:
            counts[chunk.attachment_id] = counts.get(chunk.attachment_id, 0) + 1
        return counts

    @staticmethod
    def _is_chunkable(mime_type: str) -> bool:
        if mime_type.startswith("image/"):
            return False
        if mime_type.startswith("video/"):
            return False
        return True

    def _rank_chunks_lexical(
        self,
        chunks: list[AttachmentChunk],
        query: str,
    ) -> list[tuple[AttachmentChunk, float]]:
        """Rank chunks using lexical (text token) matching."""
        scored: list[tuple[AttachmentChunk, float]] = []

        for chunk in chunks:
            score = self._lexical_score(query, chunk.content_chunk)

            # Drop zero-score matches so the prompt stays clean.
            if score <= 0:
                continue
            scored.append((chunk, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _lexical_score(self, query: str, chunk: str) -> float:
        q_tokens = self._tokenize(query)
        c_tokens = self._tokenize(chunk)
        if not q_tokens or not c_tokens:
            return 0.0

        q_counts = Counter(q_tokens)
        c_counts = Counter(c_tokens)

        shared = 0
        for token, q_count in q_counts.items():
            shared += min(q_count, c_counts.get(token, 0))

        return shared / max(1, len(q_tokens))

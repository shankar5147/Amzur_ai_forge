"""ChromaDB service for vector embedding storage and retrieval."""

from __future__ import annotations

import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.core.config import settings


class ChromaDBService:
    """Manages ChromaDB client and vector operations."""

    _client = None
    _collection = None

    @classmethod
    def get_client(cls) -> chromadb.Client:
        """Get or create ChromaDB client."""
        if cls._client is None:
            chroma_path = Path(settings.chroma_db_path)
            chroma_path.mkdir(parents=True, exist_ok=True)

            chroma_settings = Settings(
                is_persistent=True,
                persist_directory=str(chroma_path),
                anonymized_telemetry=False,
            )
            cls._client = chromadb.Client(chroma_settings)

        return cls._client

    @classmethod
    def get_collection(cls) -> chromadb.Collection:
        """Get or create embeddings collection."""
        if cls._collection is None:
            client = cls.get_client()
            cls._collection = client.get_or_create_collection(
                name="attachment_embeddings",
                metadata={"hnsw:space": "cosine"},
            )

        return cls._collection

    @classmethod
    async def add_embeddings(
        cls,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add embeddings to ChromaDB.

        Args:
            chunk_ids: Unique identifiers for chunks
            embeddings: List of embedding vectors
            documents: List of chunk text contents
            metadatas: Optional list of metadata dicts per chunk
        """
        if not chunk_ids or not embeddings or not documents:
            return

        collection = cls.get_collection()

        # Filter out None embeddings
        valid_indices = [i for i, emb in enumerate(embeddings) if emb is not None]
        if not valid_indices:
            return

        filtered_ids = [chunk_ids[i] for i in valid_indices]
        filtered_embeddings = [embeddings[i] for i in valid_indices]
        filtered_documents = [documents[i] for i in valid_indices]
        filtered_metadatas = (
            [metadatas[i] for i in valid_indices] if metadatas else None
        )

        collection.add(
            ids=filtered_ids,
            embeddings=filtered_embeddings,
            documents=filtered_documents,
            metadatas=filtered_metadatas,
        )

    @classmethod
    async def query_embeddings(
        cls,
        query_embedding: list[float],
        n_results: int = 6,
        where: dict | None = None,
    ) -> dict:
        """Query ChromaDB for similar embeddings.

        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            where: Optional metadata filter

        Returns:
            Dict with 'ids', 'documents', 'distances', 'metadatas'
        """
        if not query_embedding:
            return {"ids": [], "documents": [], "distances": [], "metadatas": []}

        collection = cls.get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )

        # Flatten single query results
        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
        }

    @classmethod
    async def delete_by_attachment(cls, attachment_id: uuid.UUID) -> None:
        """Delete all embeddings for an attachment.

        Args:
            attachment_id: UUID of the attachment
        """
        collection = cls.get_collection()
        collection.delete(
            where={"attachment_id": str(attachment_id)},
        )

    @classmethod
    async def clear(cls) -> None:
        """Clear all embeddings (useful for testing)."""
        if cls._collection is not None:
            cls._collection.delete_all()

    @classmethod
    def reset(cls) -> None:
        """Reset client and collection (useful for testing)."""
        cls._client = None
        cls._collection = None

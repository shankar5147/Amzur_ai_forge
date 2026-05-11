# RAG Enhancement for Multiple Attachments

This document describes how to implement RAG (Retrieval-Augmented Generation) functionality for multiple attachments.

## Current Architecture

### How Attachments Are Used Today

1. **Chat Endpoint** receives attachment IDs
2. **AttachmentAIService** builds context from attachments
3. **LLM** receives context as part of prompt

```python
# From chat route
attachment_contexts: list[str] = []
if attachments:
    ai_service = AttachmentAIService()
    attachment_contexts = await ai_service.build_context_blocks(attachments, service)

response = await service.generate_response(
    payload.message or "",
    history=recent_messages,
    attachment_contexts=attachment_contexts,
)
```

## Enhanced RAG Implementation

### Phase 1: Vector Store Setup

#### 1. Database Schema Extensions

Add new tables to store embeddings:

```sql
CREATE TABLE attachment_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attachment_id UUID NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content_chunk TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI embedding dimension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(attachment_id, chunk_index)
);

CREATE INDEX ON attachment_embeddings USING HNSW (embedding) WITH (m=16, ef_construction=200);

CREATE TABLE attachment_metadata (
    attachment_id UUID PRIMARY KEY REFERENCES attachments(id) ON DELETE CASCADE,
    file_type VARCHAR(50),
    page_count INT,
    word_count INT,
    language_detected VARCHAR(10),
    processing_status VARCHAR(20),  -- pending, processing, completed, failed
    processing_error TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

#### 2. Vector Database Integration

Add to requirements.txt:

```
pgvector>=0.1.8
openai>=1.0.0
pypdf>=3.14.0
pptx>=0.6.21
python-docx>=0.8.11
```

#### 3. Embedding Service

```python
# backend/app/services/embedding_service.py

from typing import Optional
from openai import OpenAI, AsyncOpenAI
from app.core.config import settings

class EmbeddingService:
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.max_tokens = 8191

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text chunk"""
        # Truncate if needed
        if len(text) > self.max_tokens * 4:  # Rough token estimate
            text = text[:self.max_tokens * 4]

        response = await self.client.embeddings.create(
            input=text,
            model=self.model
        )
        return response.data[0].embedding

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 50
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently"""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                input=batch,
                model=self.model
            )
            for item in response.data:
                all_embeddings.append(item.embedding)

        return all_embeddings
```

### Phase 2: Document Processing

#### 1. Content Extraction Service

```python
# backend/app/services/document_processor_service.py

import io
import pypdf
from docx import Document
from pptx import Presentation
from pathlib import Path

class DocumentProcessorService:
    def __init__(self, max_chunk_size: int = 1000):
        self.max_chunk_size = max_chunk_size

    async def extract_text(self, file_path: str, mime_type: str) -> str:
        """Extract text from various file formats"""
        path = Path(file_path)

        if mime_type == "application/pdf":
            return await self._extract_pdf(path)
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ]:
            return await self._extract_docx(path)
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint"
        ]:
            return await self._extract_pptx(path)
        elif mime_type in ["text/plain", "text/markdown", "application/json"]:
            return path.read_text(encoding="utf-8", errors="ignore")
        elif mime_type == "text/csv":
            return path.read_text(encoding="utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported format: {mime_type}")

    async def _extract_pdf(self, path: Path) -> str:
        """Extract text from PDF"""
        text = []
        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
        except Exception as e:
            raise ValueError(f"Failed to extract PDF: {str(e)}")
        return "\n".join(text)

    async def _extract_docx(self, path: Path) -> str:
        """Extract text from DOCX"""
        try:
            doc = Document(path)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            raise ValueError(f"Failed to extract DOCX: {str(e)}")

    async def _extract_pptx(self, path: Path) -> str:
        """Extract text from PPTX"""
        text = []
        try:
            prs = Presentation(path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
        except Exception as e:
            raise ValueError(f"Failed to extract PPTX: {str(e)}")
        return "\n".join(text)

    def chunk_text(self, text: str, overlap: int = 100) -> list[str]:
        """Split text into chunks with overlap"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.max_chunk_size
            chunk = text[start:end]
            chunks.append(chunk.strip())

            start = end - overlap

        return chunks
```

#### 2. Attachment Processing Pipeline

```python
# backend/app/services/attachment_rag_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_models import Attachment, AttachmentEmbedding, AttachmentMetadata
from app.services.embedding_service import EmbeddingService
from app.services.document_processor_service import DocumentProcessorService
from app.services.file_storage_service import FileStorageService

class AttachmentRAGService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.processor = DocumentProcessorService()
        self.embedding_service = EmbeddingService()
        self.storage = FileStorageService()

    async def process_attachment(
        self,
        attachment: Attachment,
    ) -> None:
        """Process single attachment: extract, chunk, embed"""
        try:
            # Extract text
            file_path = str(self.storage.resolve_path(attachment.file_path))
            text = await self.processor.extract_text(file_path, attachment.mime_type)

            # Chunk text
            chunks = self.processor.chunk_text(text)

            if not chunks:
                raise ValueError("No content extracted from file")

            # Generate embeddings
            embeddings = await self.embedding_service.generate_embeddings_batch(chunks)

            # Store chunks and embeddings
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                embedding_record = AttachmentEmbedding(
                    attachment_id=attachment.id,
                    chunk_index=idx,
                    content_chunk=chunk,
                    embedding=embedding,
                    metadata={
                        "chunk_count": len(chunks),
                        "word_count": len(chunk.split()),
                        "char_count": len(chunk),
                    }
                )
                self.db.add(embedding_record)

            # Update metadata
            metadata = AttachmentMetadata(
                attachment_id=attachment.id,
                file_type=attachment.mime_type.split("/")[-1],
                word_count=len(text.split()),
                processing_status="completed",
            )
            self.db.add(metadata)
            await self.db.commit()

        except Exception as e:
            # Store error in metadata
            metadata = AttachmentMetadata(
                attachment_id=attachment.id,
                processing_status="failed",
                processing_error=str(e),
            )
            self.db.add(metadata)
            await self.db.commit()

    async def process_attachments_batch(
        self,
        attachments: list[Attachment],
    ) -> None:
        """Process multiple attachments in parallel"""
        import asyncio
        tasks = [self.process_attachment(att) for att in attachments]
        await asyncio.gather(*tasks)
```

### Phase 3: Semantic Search

#### 1. Vector Search Queries

```python
# backend/app/services/rag_retriever_service.py

from sqlalchemy import func
from pgvector.sqlalchemy import Vector
from app.models.db_models import AttachmentEmbedding

class RAGRetrieverService:
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embedding_service = embedding_service

    async def retrieve_similar_chunks(
        self,
        query: str,
        attachment_ids: list[UUID],
        top_k: int = 5,
        similarity_threshold: float = 0.5,
    ) -> list[AttachmentEmbedding]:
        """Find most relevant chunks from attachments using vector similarity"""

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        # Calculate similarity
        similarity = func.cosine_similarity(
            AttachmentEmbedding.embedding,
            query_embedding
        )

        # Query
        stmt = (
            select(AttachmentEmbedding)
            .where(AttachmentEmbedding.attachment_id.in_(attachment_ids))
            .order_by(similarity.desc())
            .limit(top_k)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def retrieve_by_attachment(
        self,
        attachment_ids: list[UUID],
        limit: int = 5,
    ) -> dict[UUID, list[str]]:
        """Get top chunks from each attachment"""

        results = {}
        for att_id in attachment_ids:
            stmt = (
                select(AttachmentEmbedding)
                .where(AttachmentEmbedding.attachment_id == att_id)
                .order_by(AttachmentEmbedding.chunk_index)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            chunks = [row.content_chunk for row in result.scalars().all()]
            results[att_id] = chunks

        return results
```

#### 2. Enhanced Chat with RAG

```python
# Update backend/app/api/routes/chat.py

@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # ... existing code ...

    # Enhanced: Use RAG for better context
    attachment_contexts: list[str] = []
    if attachments:
        rag_retriever = RAGRetrieverService(db, EmbeddingService())

        # Get most relevant chunks
        relevant_chunks = await rag_retriever.retrieve_similar_chunks(
            query=payload.message or "",
            attachment_ids=[att.id for att in attachments],
            top_k=10,
        )

        # Group by attachment
        by_attachment = {}
        for chunk in relevant_chunks:
            if chunk.attachment_id not in by_attachment:
                by_attachment[chunk.attachment_id] = []
            by_attachment[chunk.attachment_id].append(chunk.content_chunk)

        # Build context blocks
        for att in attachments:
            chunks = by_attachment.get(att.id, [])
            if chunks:
                context = f"\n\n--- From {att.file_name} ---\n" + "\n".join(chunks[:3])
                attachment_contexts.append(context)

    # ... rest of chat handling ...
```

## Database Migrations

### Create Migration File

```sql
-- Migration: add_rag_tables.sql

BEGIN;

-- Vector extension (requires pgvector extension installed)
CREATE EXTENSION IF NOT EXISTS vector;

-- Attachment embeddings table
CREATE TABLE attachment_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attachment_id UUID NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content_chunk TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(attachment_id, chunk_index)
);

CREATE INDEX idx_attachment_embeddings_attachment_id
    ON attachment_embeddings(attachment_id);

CREATE INDEX idx_attachment_embeddings_embedding
    ON attachment_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=200);

-- Attachment metadata table
CREATE TABLE attachment_metadata (
    attachment_id UUID PRIMARY KEY REFERENCES attachments(id) ON DELETE CASCADE,
    file_type VARCHAR(50),
    page_count INT,
    word_count INT,
    language_detected VARCHAR(10),
    processing_status VARCHAR(20) DEFAULT 'pending',
    processing_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_attachment_metadata_status
    ON attachment_metadata(processing_status);

COMMIT;
```

## Background Task Processing

Add to Celery/task queue (optional for async processing):

```python
# backend/app/tasks/process_attachments.py

from celery import shared_task
from app.services.attachment_rag_service import AttachmentRAGService
from app.core.database import get_db

@shared_task(bind=True, max_retries=3)
def process_attachment_embeddings(self, attachment_id: str):
    """Background task to process attachment embeddings"""
    try:
        # Get DB session
        async_session = get_async_session()

        async def _process():
            async with async_session() as db:
                # Get attachment
                attachment = await db.get(Attachment, attachment_id)
                if not attachment:
                    return

                # Process
                rag_service = AttachmentRAGService(db)
                await rag_service.process_attachment(attachment)

        # Run async task
        import asyncio
        asyncio.run(_process())

    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## Frontend Enhancement

### Display RAG Status

```typescript
// frontend/src/components/AttachmentUploader.tsx

// Add processing status indicator
{item.status === "uploaded" && (
  <div className="mt-1 text-xs text-(--muted)">
    Processing for search...
  </div>
)}
```

### Query Execution

```typescript
// frontend/src/services/chatApi.ts

export async function retrieveAttachmentContext(
  threadId: string,
  query: string,
  attachmentIds: string[],
): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/chat/attachment-context`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      thread_id: threadId,
      query,
      attachment_ids: attachmentIds,
    }),
  });
  return handleResponse<string[]>(response);
}
```

## Configuration

Add to `.env`:

```bash
# RAG Configuration
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=100
RAG_SIMILARITY_THRESHOLD=0.5
```

## Performance Considerations

1. **Embedding Generation**: ~1-2 seconds per 1000 tokens
2. **Batch Processing**: Use task queue for background processing
3. **Vector Index**: HNSW index for fast similarity search (~0.1ms per query)
4. **Cache Results**: Store generated embeddings to avoid recomputation

## Future Enhancements

1. **Hybrid Search**: Combine keyword + semantic search
2. **Multi-Modal**: Support image and audio embeddings
3. **Re-ranking**: Use LLM to re-rank retrieved chunks
4. **Query Expansion**: Expand user queries for better retrieval
5. **Feedback Loop**: Learn from user interactions

---

**Version**: 2.0.0 (Proposed)
**Status**: Design Phase

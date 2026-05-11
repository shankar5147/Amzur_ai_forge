from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import AttachmentOut, AttachmentPreviewResponse, UploadAttachmentsResponse
from app.services.attachment_preview_service import AttachmentPreviewService
from app.services.attachment_service import AttachmentService
from app.services.file_storage_service import (
    FileSizeLimitExceededError,
    FileStorageError,
    FileStorageService,
    UnsafeFileError,
    UnsupportedFileTypeError,
)

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("/upload", response_model=UploadAttachmentsResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachments(
    thread_id: uuid.UUID = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadAttachmentsResponse:
    service = AttachmentService(db)
    storage = FileStorageService()

    try:
        # Validate batch before processing
        storage.validate_batch_upload(files)
        await storage.validate_batch_sizes(files)
        
        attachments = await service.upload_files_for_thread(
            thread_id=thread_id,
            user_id=current_user.id,
            files=files,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except FileSizeLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsafeFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not attachments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

    return UploadAttachmentsResponse(attachments=[AttachmentOut.model_validate(item) for item in attachments])


@router.get("/thread/{thread_id}", response_model=UploadAttachmentsResponse)
async def list_thread_attachments(
    thread_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadAttachmentsResponse:
    service = AttachmentService(db)
    attachments = await service.list_thread_attachments(thread_id=thread_id, user_id=current_user.id)
    return UploadAttachmentsResponse(attachments=[AttachmentOut.model_validate(item) for item in attachments])


@router.get("/{attachment_id}/preview", response_model=AttachmentPreviewResponse)
async def get_attachment_preview(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttachmentPreviewResponse:
    service = AttachmentService(db)
    attachment = await service.get_attachment_for_user(attachment_id=attachment_id, user_id=current_user.id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    preview_service = AttachmentPreviewService()
    preview = await preview_service.build_preview(attachment)
    return AttachmentPreviewResponse(
        attachment_id=attachment.id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        preview_type=preview.preview_type,
        columns=preview.columns,
        rows=preview.rows,
        content=preview.content,
        truncated=preview.truncated,
    )

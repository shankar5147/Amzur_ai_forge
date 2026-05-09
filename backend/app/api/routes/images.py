from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import ImageGenerationRequest, ImageGenerationResponse, MessageOut
from app.services.image_generation_service import (
    ImageGenerationError,
    ImageGenerationService,
    ImageRateLimitError,
    PromptValidationError,
)
from app.services.message_service import MessageService

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("/generate", response_model=ImageGenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_image(
    payload: ImageGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageGenerationResponse:
    service = ImageGenerationService(db)

    try:
        thread, user_message, assistant_message, generated = await service.generate_for_chat(
            user_id=current_user.id,
            prompt=payload.prompt,
            thread_id=payload.thread_id,
            message=payload.message,
        )
    except PromptValidationError as exc:
        detail = str(exc)
        if detail == "Thread not found.":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except ImageRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ImageGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    msg_service = MessageService(db)
    user_msg = await msg_service.get_message_with_attachments(user_message.id)
    assistant_msg = await msg_service.get_message_with_attachments(assistant_message.id)

    return ImageGenerationResponse(
        thread_id=thread.id,
        user_message=MessageOut.model_validate(user_msg or user_message),
        assistant_message=MessageOut.model_validate(assistant_msg or assistant_message),
        image=generated,
    )

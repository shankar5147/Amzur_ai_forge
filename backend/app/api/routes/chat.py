import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import ChatHistoryResponse, ChatRequest, ChatResponse, MessageOut
from app.services.attachment_ai_service import AttachmentAIService
from app.services.attachment_service import AttachmentService
from app.services.chat_service import ChatService, LLMServiceError
from app.services.message_service import MessageService
from app.services.thread_service import ThreadService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    thread_service = ThreadService(db)
    attachment_service = AttachmentService(db)

    # If no thread_id provided, create a new thread
    if payload.thread_id is None:
        thread = await thread_service.create_thread(current_user.id, "New Chat")
    else:
        thread = await thread_service.get_thread(payload.thread_id, current_user.id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

    # Fetch last 5 messages for conversational memory
    msg_service = MessageService(db)
    recent_messages = await msg_service.get_recent_history(thread.id, limit=5)

    if payload.attachment_ids:
        attachments = await attachment_service.get_attachments_by_ids(
            thread_id=thread.id,
            user_id=current_user.id,
            attachment_ids=payload.attachment_ids,
        )
        if len(attachments) != len(payload.attachment_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more attachments are invalid.")
    else:
        # Follow-up questions should still be able to use uploaded files in the same thread.
        thread_attachments = await attachment_service.list_thread_attachments(thread_id=thread.id, user_id=current_user.id)
        max_items = max(1, settings.max_attachment_context_items)
        attachments = thread_attachments[-max_items:]

    try:
        service = ChatService()
        attachment_contexts: list[str] = []
        if attachments:
            ai_service = AttachmentAIService()
            attachment_contexts = await ai_service.build_context_blocks(attachments, service)

        response = await service.generate_response(
            payload.message or "",
            history=recent_messages,
            attachment_contexts=attachment_contexts,
        )
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Persist both messages
    user_msg = await msg_service.save_message(thread.id, current_user.id, "user", payload.message or "")
    await attachment_service.attach_to_message(
        thread_id=thread.id,
        user_id=current_user.id,
        message_id=user_msg.id,
        attachment_ids=payload.attachment_ids,
    )
    await msg_service.save_message(thread.id, current_user.id, "assistant", response)

    # Auto-generate thread name when the thread still has the default title.
    should_update_name = bool(payload.message) and thread.name.strip().lower() == "new chat"
    if should_update_name:
        try:
            name = await service.generate_thread_name(payload.message)
            await thread_service.update_thread(thread.id, current_user.id, name)
        except Exception:
            pass  # Non-critical, keep default name

    return ChatResponse(response=response, thread_id=thread.id)


@router.get("/history/{thread_id}", response_model=ChatHistoryResponse)
async def chat_history(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    # Verify thread belongs to user
    thread_service = ThreadService(db)
    thread = await thread_service.get_thread(uuid.UUID(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

    msg_service = MessageService(db)
    messages = await msg_service.get_history(uuid.UUID(thread_id))
    return ChatHistoryResponse(
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                attachments=[a for a in m.attachments],
            )
            for m in messages
        ]
    )

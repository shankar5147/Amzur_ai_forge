import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import ChatHistoryResponse, ChatRequest, ChatResponse, MessageOut
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

    try:
        service = ChatService()
        response = await service.generate_response(payload.message, history=recent_messages)
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Persist both messages
    await msg_service.save_message(thread.id, current_user.id, "user", payload.message)
    await msg_service.save_message(thread.id, current_user.id, "assistant", response)

    # Auto-generate thread name on first message (when thread was just created)
    if payload.thread_id is None:
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
        messages=[MessageOut.model_validate(m) for m in messages]
    )

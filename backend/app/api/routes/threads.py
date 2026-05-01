from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import ThreadCreate, ThreadListResponse, ThreadOut, ThreadUpdate
from app.services.thread_service import ThreadService

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.post("", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    service = ThreadService(db)
    thread = await service.create_thread(current_user.id, payload.name)
    return ThreadOut.model_validate(thread)


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadListResponse:
    service = ThreadService(db)
    threads = await service.get_threads(current_user.id)
    return ThreadListResponse(threads=[ThreadOut.model_validate(t) for t in threads])


@router.patch("/{thread_id}", response_model=ThreadOut)
async def update_thread(
    thread_id: str,
    payload: ThreadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    import uuid
    service = ThreadService(db)
    thread = await service.update_thread(uuid.UUID(thread_id), current_user.id, payload.name)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    return ThreadOut.model_validate(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    import uuid
    service = ThreadService(db)
    deleted = await service.delete_thread(uuid.UUID(thread_id), current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

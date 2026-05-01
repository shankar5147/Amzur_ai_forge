"""Tests for thread service layer."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import User
from app.services.thread_service import ThreadService


class TestCreateThread:
    @pytest.mark.asyncio
    async def test_create_thread_default_name(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        thread = await service.create_thread(test_user.id)
        assert thread.name == "New Chat"
        assert thread.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_create_thread_custom_name(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        thread = await service.create_thread(test_user.id, "My Topic")
        assert thread.name == "My Topic"


class TestGetThreads:
    @pytest.mark.asyncio
    async def test_empty_threads(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        threads = await service.get_threads(test_user.id)
        assert threads == []

    @pytest.mark.asyncio
    async def test_returns_user_threads_ordered_by_updated_at(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        t1 = await service.create_thread(test_user.id, "First")
        t2 = await service.create_thread(test_user.id, "Second")
        threads = await service.get_threads(test_user.id)
        assert len(threads) == 2
        # Most recent first
        assert threads[0].id == t2.id

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_threads(self, db_session: AsyncSession, test_user: User):
        other_user = User(
            id=uuid.uuid4(), email="other@amzur.com",
            hashed_password="hashed", full_name="Other"
        )
        db_session.add(other_user)
        await db_session.commit()

        service = ThreadService(db_session)
        await service.create_thread(other_user.id, "Other's thread")
        threads = await service.get_threads(test_user.id)
        assert len(threads) == 0


class TestGetThread:
    @pytest.mark.asyncio
    async def test_get_existing_thread(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        created = await service.create_thread(test_user.id, "Test")
        found = await service.get_thread(created.id, test_user.id)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        found = await service.get_thread(uuid.uuid4(), test_user.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_other_users_thread_returns_none(self, db_session: AsyncSession, test_user: User):
        other_user = User(
            id=uuid.uuid4(), email="other2@amzur.com",
            hashed_password="hashed", full_name="Other"
        )
        db_session.add(other_user)
        await db_session.commit()

        service = ThreadService(db_session)
        thread = await service.create_thread(other_user.id, "Private")
        found = await service.get_thread(thread.id, test_user.id)
        assert found is None


class TestUpdateThread:
    @pytest.mark.asyncio
    async def test_update_thread_name(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        thread = await service.create_thread(test_user.id, "Old Name")
        updated = await service.update_thread(thread.id, test_user.id, "New Name")
        assert updated is not None
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        result = await service.update_thread(uuid.uuid4(), test_user.id, "Name")
        assert result is None


class TestDeleteThread:
    @pytest.mark.asyncio
    async def test_delete_thread(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        thread = await service.create_thread(test_user.id, "To Delete")
        deleted = await service.delete_thread(thread.id, test_user.id)
        assert deleted is True
        # Verify it's gone
        found = await service.get_thread(thread.id, test_user.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, db_session: AsyncSession, test_user: User):
        service = ThreadService(db_session)
        deleted = await service.delete_thread(uuid.uuid4(), test_user.id)
        assert deleted is False

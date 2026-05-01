"""Tests for message service layer."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Thread, User
from app.services.message_service import MessageService
from app.services.thread_service import ThreadService


class TestSaveMessage:
    @pytest.mark.asyncio
    async def test_save_message(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Test Thread")

        msg_svc = MessageService(db_session)
        msg = await msg_svc.save_message(thread.id, test_user.id, "user", "Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.thread_id == thread.id
        assert msg.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_save_assistant_message(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Thread")

        msg_svc = MessageService(db_session)
        msg = await msg_svc.save_message(thread.id, test_user.id, "assistant", "Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_empty_history(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Empty")

        msg_svc = MessageService(db_session)
        history = await msg_svc.get_history(thread.id)
        assert history == []

    @pytest.mark.asyncio
    async def test_history_returns_ordered_messages(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Chat")

        msg_svc = MessageService(db_session)
        await msg_svc.save_message(thread.id, test_user.id, "user", "First")
        await msg_svc.save_message(thread.id, test_user.id, "assistant", "Second")
        await msg_svc.save_message(thread.id, test_user.id, "user", "Third")

        history = await msg_svc.get_history(thread.id)
        assert len(history) == 3
        assert history[0].content == "First"
        assert history[1].content == "Second"
        assert history[2].content == "Third"

    @pytest.mark.asyncio
    async def test_history_scoped_to_thread(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread1 = await thread_svc.create_thread(test_user.id, "Thread 1")
        thread2 = await thread_svc.create_thread(test_user.id, "Thread 2")

        msg_svc = MessageService(db_session)
        await msg_svc.save_message(thread1.id, test_user.id, "user", "In thread 1")
        await msg_svc.save_message(thread2.id, test_user.id, "user", "In thread 2")

        history1 = await msg_svc.get_history(thread1.id)
        history2 = await msg_svc.get_history(thread2.id)
        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0].content == "In thread 1"
        assert history2[0].content == "In thread 2"


class TestGetRecentHistory:
    @pytest.mark.asyncio
    async def test_returns_last_n_messages(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Chat")

        msg_svc = MessageService(db_session)
        for i in range(10):
            await msg_svc.save_message(thread.id, test_user.id, "user", f"Message {i}")

        recent = await msg_svc.get_recent_history(thread.id, limit=5)
        assert len(recent) == 5
        # Should be the last 5 in chronological order
        assert recent[0].content == "Message 5"
        assert recent[4].content == "Message 9"

    @pytest.mark.asyncio
    async def test_returns_all_when_fewer_than_limit(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Chat")

        msg_svc = MessageService(db_session)
        await msg_svc.save_message(thread.id, test_user.id, "user", "Only one")

        recent = await msg_svc.get_recent_history(thread.id, limit=5)
        assert len(recent) == 1
        assert recent[0].content == "Only one"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_messages(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Empty")

        msg_svc = MessageService(db_session)
        recent = await msg_svc.get_recent_history(thread.id, limit=5)
        assert recent == []

    @pytest.mark.asyncio
    async def test_preserves_chronological_order(self, db_session: AsyncSession, test_user: User):
        thread_svc = ThreadService(db_session)
        thread = await thread_svc.create_thread(test_user.id, "Chat")

        msg_svc = MessageService(db_session)
        await msg_svc.save_message(thread.id, test_user.id, "user", "Q1")
        await msg_svc.save_message(thread.id, test_user.id, "assistant", "A1")
        await msg_svc.save_message(thread.id, test_user.id, "user", "Q2")

        recent = await msg_svc.get_recent_history(thread.id, limit=5)
        assert recent[0].role == "user"
        assert recent[0].content == "Q1"
        assert recent[1].role == "assistant"
        assert recent[1].content == "A1"
        assert recent[2].role == "user"
        assert recent[2].content == "Q2"

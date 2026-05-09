"""Tests for chat API routes."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.db_models import User


class TestChatEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_creates_new_thread(self, MockChatService, client: AsyncClient, auth_headers: dict):
        mock_instance = MockChatService.return_value
        mock_instance.generate_response = AsyncMock(return_value="AI says hello!")
        mock_instance.generate_thread_name = AsyncMock(return_value="Greeting Chat")

        resp = await client.post("/api/chat", json={"message": "Hello AI"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "AI says hello!"
        assert "thread_id" in data

    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_existing_thread(self, MockChatService, client: AsyncClient, auth_headers: dict):
        mock_instance = MockChatService.return_value
        mock_instance.generate_response = AsyncMock(return_value="Follow up response.")

        # Create thread first
        create_resp = await client.post("/api/threads", json={"name": "Existing"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        resp = await client.post("/api/chat", json={
            "message": "Follow up",
            "thread_id": thread_id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == thread_id

    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_nonexistent_thread(self, MockChatService, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/chat", json={
            "message": "Hello",
            "thread_id": str(uuid.uuid4()),
        }, headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_llm_error(self, MockChatService, client: AsyncClient, auth_headers: dict):
        from app.services.chat_service import LLMServiceError
        mock_instance = MockChatService.return_value
        mock_instance.generate_response = AsyncMock(side_effect=LLMServiceError("LLM down"))

        # Create a thread to avoid 404
        create_resp = await client.post("/api/threads", json={"name": "T"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        resp = await client.post("/api/chat", json={
            "message": "Hello",
            "thread_id": thread_id,
        }, headers=auth_headers)
        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_chat_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/chat", json={"message": "Hello"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/chat", json={"message": ""}, headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.routes.chat.AttachmentAIService")
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_uses_thread_attachments_when_ids_not_provided(
        self,
        MockChatService,
        MockAttachmentAIService,
        client: AsyncClient,
        auth_headers: dict,
    ):
        mock_chat = MockChatService.return_value
        mock_chat.generate_response = AsyncMock(return_value="Answer from CSV context")

        mock_ai = MockAttachmentAIService.return_value
        mock_ai.build_context_blocks = AsyncMock(return_value=["[Table attachment context]"])

        create_resp = await client.post("/api/threads", json={"name": "New Chat"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        upload_resp = await client.post(
            "/api/attachments/upload",
            headers=auth_headers,
            data={"thread_id": thread_id},
            files={"files": ("sales.csv", b"month,revenue\nJan,100", "text/csv")},
        )
        assert upload_resp.status_code == 201

        resp = await client.post(
            "/api/chat",
            json={"message": "What is Jan revenue?", "thread_id": thread_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        mock_ai.build_context_blocks.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_chat_updates_default_thread_name_on_existing_thread(
        self,
        MockChatService,
        client: AsyncClient,
        auth_headers: dict,
    ):
        mock_chat = MockChatService.return_value
        mock_chat.generate_response = AsyncMock(return_value="Done")
        mock_chat.generate_thread_name = AsyncMock(return_value="Revenue by Month")

        create_resp = await client.post("/api/threads", json={"name": "New Chat"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        chat_resp = await client.post(
            "/api/chat",
            json={"message": "Analyze revenue trends", "thread_id": thread_id},
            headers=auth_headers,
        )
        assert chat_resp.status_code == 200

        threads_resp = await client.get("/api/threads", headers=auth_headers)
        assert threads_resp.status_code == 200
        thread = next(t for t in threads_resp.json()["threads"] if t["id"] == thread_id)
        assert thread["name"] == "Revenue by Month"


class TestChatHistoryEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_get_history(self, MockChatService, client: AsyncClient, auth_headers: dict):
        mock_instance = MockChatService.return_value
        mock_instance.generate_response = AsyncMock(return_value="Response")
        mock_instance.generate_thread_name = AsyncMock(return_value="Name")

        # Send message to create thread with messages
        chat_resp = await client.post("/api/chat", json={"message": "Test"}, headers=auth_headers)
        thread_id = chat_resp.json()["thread_id"]

        # Get history
        resp = await client.get(f"/api/chat/history/{thread_id}", headers=auth_headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test"
        assert messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_history_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/chat/history/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_unauthenticated(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/chat/history/{fake_id}")
        assert resp.status_code == 401

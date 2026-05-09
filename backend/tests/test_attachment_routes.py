from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestAttachmentUploadEndpoint:
    @pytest.mark.asyncio
    async def test_upload_text_file(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post("/api/threads", json={"name": "Files"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        files = {
            "files": ("notes.txt", b"hello world", "text/plain"),
        }
        data = {"thread_id": thread_id}

        resp = await client.post("/api/attachments/upload", headers=auth_headers, data=data, files=files)
        assert resp.status_code == 201
        payload = resp.json()
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["file_name"] == "notes.txt"

    @pytest.mark.asyncio
    async def test_upload_rejects_executable(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post("/api/threads", json={"name": "Files"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        files = {
            "files": ("payload.bin", b"MZ\x00\x01\x02", "application/octet-stream"),
        }
        data = {"thread_id": thread_id}

        resp = await client.post("/api/attachments/upload", headers=auth_headers, data=data, files=files)
        assert resp.status_code == 400


class TestChatWithAttachments:
    @pytest.mark.asyncio
    @patch("app.api.routes.chat.ChatService")
    async def test_attachment_only_message(self, MockChatService, client: AsyncClient, auth_headers: dict):
        mock_instance = MockChatService.return_value
        mock_instance.generate_response = AsyncMock(return_value="I analyzed your file.")
        mock_instance.generate_thread_name = AsyncMock(return_value="Files")

        create_resp = await client.post("/api/threads", json={"name": "Files"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        upload_resp = await client.post(
            "/api/attachments/upload",
            headers=auth_headers,
            data={"thread_id": thread_id},
            files={"files": ("snippet.py", b"print('hi')", "text/plain")},
        )
        attachment_id = upload_resp.json()["attachments"][0]["id"]

        chat_resp = await client.post(
            "/api/chat",
            headers=auth_headers,
            json={
                "message": None,
                "thread_id": thread_id,
                "attachment_ids": [attachment_id],
            },
        )
        assert chat_resp.status_code == 200
        assert chat_resp.json()["thread_id"] == thread_id

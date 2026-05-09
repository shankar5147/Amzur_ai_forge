from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.image_generation_service import ImageGenerationError, ImageRateLimitError, PromptValidationError


class TestImageGenerationRoute:
    @pytest.mark.asyncio
    @patch("app.api.routes.images.ImageGenerationService")
    async def test_generate_image_success(self, MockService, client: AsyncClient, auth_headers: dict):
        mock_service = MockService.return_value

        thread_id = uuid.uuid4()
        user_msg_id = uuid.uuid4()
        assistant_msg_id = uuid.uuid4()
        image_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        thread = MagicMock(id=thread_id)
        user_message = MagicMock(id=user_msg_id)
        assistant_message = MagicMock(id=assistant_msg_id)
        generated = MagicMock(
            id=image_id,
            user_id=user_id,
            thread_id=thread_id,
            prompt="Generate an image of a futuristic city",
            image_url=f"{thread_id}/generated.png",
            created_at=now,
        )
        mock_service.generate_for_chat = AsyncMock(
            return_value=(thread, user_message, assistant_message, generated)
        )

        with patch("app.api.routes.images.MessageService") as MockMessageService:
            mock_msg_service = MockMessageService.return_value
            mock_msg_service.get_message_with_attachments = AsyncMock(
                side_effect=[
                    MagicMock(id=user_msg_id, role="user", content="Generate image", created_at=now, attachments=[]),
                    MagicMock(
                        id=assistant_msg_id,
                        role="assistant",
                        content="Generated image based on your prompt.",
                        created_at=now,
                        attachments=[
                            MagicMock(
                                id=uuid.uuid4(),
                                thread_id=thread_id,
                                message_id=assistant_msg_id,
                                file_name="generated_image.png",
                                mime_type="image/png",
                                file_path=f"{thread_id}/generated.png",
                                created_at=now,
                            )
                        ],
                    ),
                ]
            )

            resp = await client.post(
                "/api/images/generate",
                json={"prompt": "Generate an image of a futuristic city"},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "thread_id" in body
        assert body["assistant_message"]["attachments"][0]["mime_type"].startswith("image/")

    @pytest.mark.asyncio
    @patch("app.api.routes.images.ImageGenerationService")
    async def test_generate_image_thread_not_found(self, MockService, client: AsyncClient, auth_headers: dict):
        mock_service = MockService.return_value
        mock_service.generate_for_chat = AsyncMock(side_effect=PromptValidationError("Thread not found."))

        resp = await client.post(
            "/api/images/generate",
            json={"prompt": "Create a logo", "thread_id": "00000000-0000-0000-0000-000000000001"},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.routes.images.ImageGenerationService")
    async def test_generate_image_rate_limited(self, MockService, client: AsyncClient, auth_headers: dict):
        mock_service = MockService.return_value
        mock_service.generate_for_chat = AsyncMock(side_effect=ImageRateLimitError("Rate limit"))

        resp = await client.post(
            "/api/images/generate",
            json={"prompt": "Create a logo"},
            headers=auth_headers,
        )

        assert resp.status_code == 429

    @pytest.mark.asyncio
    @patch("app.api.routes.images.ImageGenerationService")
    async def test_generate_image_provider_failure(self, MockService, client: AsyncClient, auth_headers: dict):
        mock_service = MockService.return_value
        mock_service.generate_for_chat = AsyncMock(side_effect=ImageGenerationError("Provider down"))

        resp = await client.post(
            "/api/images/generate",
            json={"prompt": "Create a logo"},
            headers=auth_headers,
        )

        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_generate_image_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/images/generate",
            json={"prompt": "Generate an image of mountains"},
        )

        assert resp.status_code == 401

    def test_modification_request_detection(self):
        """Test that modification requests are correctly detected."""
        from app.services.image_generation_service import ImageGenerationService

        assert ImageGenerationService._is_modification_request("change it car green") is True
        assert ImageGenerationService._is_modification_request("make it blue") is True
        assert ImageGenerationService._is_modification_request("update the color to red") is True
        assert ImageGenerationService._is_modification_request("modify the background") is True
        assert ImageGenerationService._is_modification_request("generate a new car") is False

    def test_prompt_merging(self):
        """Test that prompts are intelligently merged."""
        from app.services.image_generation_service import ImageGenerationService

        original = "A car driving on a long road"
        modification = "change it car green"
        merged = ImageGenerationService._merge_prompts(original, modification)
        assert "A car driving on a long road" in merged
        assert "car green" in merged

        modification2 = "make it the car blue"
        merged2 = ImageGenerationService._merge_prompts(original, modification2)
        assert "A car driving on a long road" in merged2
        assert "the car blue" in merged2

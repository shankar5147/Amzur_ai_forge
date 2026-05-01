"""Tests for chat service layer (LLM interaction)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.services.chat_service import ChatService, LLMServiceError


class TestChatService:
    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_response_success(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._chain = AsyncMock()
        service._chain.ainvoke = AsyncMock(return_value="This is a test response.")

        result = await service.generate_response("Hello")
        assert result == "This is a test response."
        service._chain.ainvoke.assert_called_once_with({"message": "Hello", "history": []})

    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_response_with_history(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._chain = AsyncMock()
        service._chain.ainvoke = AsyncMock(return_value="Context-aware response.")

        # Create mock messages
        msg1 = MagicMock(role="user", content="What is Python?")
        msg2 = MagicMock(role="assistant", content="Python is a programming language.")

        result = await service.generate_response("Tell me more", history=[msg1, msg2])
        assert result == "Context-aware response."

        call_args = service._chain.ainvoke.call_args[0][0]
        assert call_args["message"] == "Tell me more"
        assert len(call_args["history"]) == 2
        assert isinstance(call_args["history"][0], HumanMessage)
        assert isinstance(call_args["history"][1], AIMessage)

    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_response_llm_failure(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._chain = AsyncMock()
        service._chain.ainvoke = AsyncMock(side_effect=Exception("LLM down"))

        with pytest.raises(LLMServiceError, match="Failed to get a response"):
            await service.generate_response("Hello")

    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_thread_name_success(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._name_chain = AsyncMock()
        service._name_chain.ainvoke = AsyncMock(return_value="  Python Basics  ")

        result = await service.generate_thread_name("What is Python?")
        assert result == "Python Basics"

    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_thread_name_fallback_on_error(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._name_chain = AsyncMock()
        service._name_chain.ainvoke = AsyncMock(side_effect=Exception("fail"))

        result = await service.generate_thread_name("Tell me about machine learning algorithms")
        # Fallback: first 5 words
        assert result == "Tell me about machine learning"

    @pytest.mark.asyncio
    @patch("app.services.chat_service.ChatService.__init__", return_value=None)
    async def test_generate_thread_name_truncates_long_names(self, mock_init):
        service = ChatService.__new__(ChatService)
        service._name_chain = AsyncMock()
        service._name_chain.ainvoke = AsyncMock(return_value="A" * 300)

        result = await service.generate_thread_name("Test")
        assert len(result) <= 255

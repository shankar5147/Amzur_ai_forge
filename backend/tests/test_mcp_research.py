"""
Tests for the MCP-powered Research Agent (Project 12).

Validates:
- MCP client helper functions
- LangGraph research agent (with mocked MCP session)
- SSE streaming endpoint produces the same event types as Project 10
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────


def _make_mcp_result(text: str, is_error: bool = False):
    """Create a fake MCP CallToolResult."""
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], isError=is_error)


def _fake_llm_response(content: str):
    """Create a fake LangChain AIMessage-like object."""
    return SimpleNamespace(content=content)


# ── MCP client unit tests ───────────────────────────────────────────


class TestMCPClientHelpers:
    """Tests for mcp_arxiv_client helper functions."""

    def test_extract_text(self):
        from app.services.mcp_arxiv_client import _extract_text

        result = _make_mcp_result("Paper: Transformers are great")
        assert _extract_text(result) == "Paper: Transformers are great"

    def test_extract_text_multiple_blocks(self):
        from app.services.mcp_arxiv_client import _extract_text

        block1 = SimpleNamespace(type="text", text="Hello")
        block2 = SimpleNamespace(type="text", text="World")
        result = SimpleNamespace(content=[block1, block2], isError=False)
        assert _extract_text(result) == "Hello\nWorld"

    @pytest.mark.asyncio
    async def test_mcp_search_papers_success(self):
        from app.services.mcp_arxiv_client import mcp_search_papers

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = _make_mcp_result(
            "Found 2 papers about transformers..."
        )

        text = await mcp_search_papers(mock_session, "transformers", max_results=5)
        assert "transformers" in text
        mock_session.call_tool.assert_called_once_with(
            "search_papers", {"query": "transformers", "max_results": 5}
        )

    @pytest.mark.asyncio
    async def test_mcp_search_papers_error(self):
        from app.services.mcp_arxiv_client import mcp_search_papers

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = _make_mcp_result(
            "Rate limited", is_error=True
        )

        with pytest.raises(RuntimeError, match="MCP search_papers error"):
            await mcp_search_papers(mock_session, "test")

    @pytest.mark.asyncio
    async def test_mcp_download_paper(self):
        from app.services.mcp_arxiv_client import mcp_download_paper

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = _make_mcp_result(
            "Downloaded paper 2401.12345"
        )

        text = await mcp_download_paper(mock_session, "2401.12345")
        assert "2401.12345" in text

    @pytest.mark.asyncio
    async def test_mcp_read_paper(self):
        from app.services.mcp_arxiv_client import mcp_read_paper

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = _make_mcp_result(
            "# Paper Title\nAbstract: This is a paper..."
        )

        text = await mcp_read_paper(mock_session, "2401.12345")
        assert "Paper Title" in text

    def test_find_server_command_fallback(self):
        """Verify _find_server_command doesn't crash."""
        from app.services.mcp_arxiv_client import _find_server_command

        cmd, args = _find_server_command()
        assert isinstance(cmd, str)
        assert isinstance(args, list)


# ── LangGraph agent tests ───────────────────────────────────────────


class TestMCPResearchAgent:
    """Tests for the LangGraph-based MCP research agent."""

    @pytest.mark.asyncio
    async def test_event_helper(self):
        from app.services.mcp_research_agent_service import _event

        evt = _event("status", {"step": "planning", "message": "Hello"})
        assert evt["event"] == "status"
        assert evt["data"]["step"] == "planning"

    @pytest.mark.asyncio
    async def test_run_mcp_research_agent_produces_events(self):
        """The agent should yield the standard SSE event types."""
        from app.services.mcp_research_agent_service import run_mcp_research_agent

        mock_session = AsyncMock()

        # Mock MCP tool calls
        mock_session.call_tool.side_effect = [
            # search_papers call 1
            _make_mcp_result(
                'Found 1 paper:\n'
                'ID: 2401.00001\n'
                'Title: Test Paper on AI Agents\n'
                'Authors: Alice, Bob\n'
                'Abstract: This paper explores AI agents.\n'
                'Published: 2024-01-15\n'
                'Categories: cs.AI\n'
            ),
            # search_papers call 2
            _make_mcp_result(
                'Found 1 paper:\n'
                'ID: 2401.00002\n'
                'Title: LLM Survey 2024\n'
                'Authors: Charlie\n'
                'Abstract: A survey of large language models.\n'
                'Published: 2024-02-01\n'
                'Categories: cs.CL\n'
            ),
            # download_paper for first paper
            _make_mcp_result("Downloaded 2401.00001"),
            # read_paper for first paper
            _make_mcp_result("Full text of AI agents paper..."),
            # download_paper for second paper
            _make_mcp_result("Downloaded 2401.00002"),
            # read_paper for second paper
            _make_mcp_result("Full text of LLM survey..."),
        ]

        # Mock LLM responses
        llm_responses = [
            # plan_searches → queries
            _fake_llm_response('["AI agents 2024", "LLM survey"]'),
            # search_papers → parse result 1
            _fake_llm_response(json.dumps([{
                "paper_id": "2401.00001",
                "title": "Test Paper on AI Agents",
                "authors": ["Alice", "Bob"],
                "abstract": "This paper explores AI agents.",
                "published": "2024-01-15",
                "updated": "2024-01-15",
                "categories": ["cs.AI"],
            }])),
            # search_papers → parse result 2
            _fake_llm_response(json.dumps([{
                "paper_id": "2401.00002",
                "title": "LLM Survey 2024",
                "authors": ["Charlie"],
                "abstract": "A survey of large language models.",
                "published": "2024-02-01",
                "updated": "2024-02-01",
                "categories": ["cs.CL"],
            }])),
            # rank_papers
            _fake_llm_response(json.dumps([
                {"index": 0, "score": 9.0},
                {"index": 1, "score": 7.5},
            ])),
            # analyze paper 1
            _fake_llm_response(json.dumps({
                "summary": "Paper about AI agents.",
                "key_findings": ["Finding 1"],
                "methodology": "Survey",
                "relevance": "high",
                "limitations": "Limited scope",
            })),
            # analyze paper 2
            _fake_llm_response(json.dumps({
                "summary": "Survey of LLMs.",
                "key_findings": ["Finding A"],
                "methodology": "Review",
                "relevance": "medium",
                "limitations": "Not comprehensive",
            })),
            # generate_digest
            _fake_llm_response("## Research Digest: AI Agents\n\nGreat research."),
        ]

        llm_mock = AsyncMock()
        llm_mock.ainvoke = AsyncMock(side_effect=llm_responses)

        collected_events: list[dict] = []

        with (
            patch(
                "app.services.mcp_research_agent_service.create_arxiv_mcp_session"
            ) as mock_ctx,
            patch(
                "app.services.mcp_research_agent_service._get_llm",
                return_value=llm_mock,
            ),
        ):
            # Make the context manager yield our mock session
            mock_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            async for evt in run_mcp_research_agent("AI agents research"):
                collected_events.append(evt)

        # Verify we got the expected event types
        event_types = [e["event"] for e in collected_events]

        assert "status" in event_types, "Should have status events"
        assert "queries" in event_types, "Should have queries event"
        assert "papers" in event_types, "Should have papers event"
        assert "paper_analysis" in event_types, "Should have paper_analysis events"
        assert "digest" in event_types, "Should have digest event"
        assert "done" in event_types, "Should have done event"

        # Verify done event has stats
        done_events = [e for e in collected_events if e["event"] == "done"]
        assert len(done_events) == 1
        assert "papers_found" in done_events[0]["data"]
        assert "papers_analyzed" in done_events[0]["data"]


# ── SSE endpoint tests ──────────────────────────────────────────────


class TestMCPResearchRoute:
    """Tests for the /api/mcp-research/stream SSE endpoint."""

    @pytest.mark.asyncio
    async def test_stream_requires_auth(self, client: AsyncClient):
        """Endpoint should reject unauthenticated requests."""
        resp = await client.get(
            "/api/mcp-research/stream", params={"topic": "AI agents"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_stream_rejects_short_topic(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Topic must be at least 3 characters."""
        resp = await client.get(
            "/api/mcp-research/stream",
            params={"topic": "AI"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_stream_produces_sse_events(
        self, client: AsyncClient, auth_headers: dict
    ):
        """The endpoint should stream SSE events when the agent runs."""

        async def _fake_agent(topic: str):
            yield {"event": "status", "data": {"step": "planning", "message": "Planning…"}}
            yield {"event": "queries", "data": {"queries": ["test query"]}}
            yield {"event": "done", "data": {"papers_found": 0, "papers_analyzed": 0}}

        with patch(
            "app.api.routes.mcp_research.run_mcp_research_agent",
            side_effect=_fake_agent,
        ):
            resp = await client.get(
                "/api/mcp-research/stream",
                params={"topic": "test topic"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        body = resp.text
        assert "event: status" in body
        assert "event: queries" in body
        assert "event: done" in body

    @pytest.mark.asyncio
    async def test_stream_handles_agent_error(
        self, client: AsyncClient, auth_headers: dict
    ):
        """If the agent raises, the endpoint should send an error + done event."""

        async def _exploding_agent(topic: str):
            raise RuntimeError("MCP server crashed")
            yield  # make it an async generator  # noqa: unreachable

        with patch(
            "app.api.routes.mcp_research.run_mcp_research_agent",
            side_effect=_exploding_agent,
        ):
            resp = await client.get(
                "/api/mcp-research/stream",
                params={"topic": "test topic"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.text
        assert "event: error" in body
        assert "event: done" in body

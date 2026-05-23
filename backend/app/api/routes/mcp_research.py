"""SSE streaming endpoint for the MCP-powered Research Digest Agent (Project 12).

Identical contract to the original ``/api/research/stream`` from Project 10 —
the only difference is that paper search / download / read is delegated to the
arxiv-mcp-server via MCP instead of using hand-written HTTP calls.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.models.db_models import User
from app.services.mcp_research_agent_service import run_mcp_research_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-research", tags=["mcp-research"])


@router.get("/stream")
async def stream_mcp_research(
    topic: Annotated[str, Query(min_length=3, max_length=500)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Stream a research digest for the given topic using Server-Sent Events.

    Uses the arxiv-mcp-server (MCP) + LangGraph under the hood, but
    produces the **exact same** SSE event types as ``/api/research/stream``:

    - status, queries, papers, paper_analysis, digest, error, done
    """

    async def event_generator():
        try:
            async for evt in run_mcp_research_agent(topic.strip()):
                event_type = evt.get("event", "message")
                data = evt.get("data", {})
                payload = json.dumps(data, default=str)
                yield f"event: {event_type}\ndata: {payload}\n\n"
        except Exception as exc:
            logger.error("MCP research agent error: %s", exc)
            error_payload = json.dumps({"message": f"MCP Agent error: {exc}"})
            yield f"event: error\ndata: {error_payload}\n\n"
            yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

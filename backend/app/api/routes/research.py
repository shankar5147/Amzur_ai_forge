"""SSE streaming endpoint for the autonomous Research Digest Agent."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.models.db_models import User
from app.services.research_agent_service import run_research_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/stream")
async def stream_research(
    topic: Annotated[str, Query(min_length=3, max_length=500)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Stream a research digest for the given topic using Server-Sent Events.

    The client receives events of the following types:
    - status   — progress updates (step name + message)
    - queries  — planned search queries
    - papers   — list of ranked papers
    - paper_analysis — analysis of a single paper
    - digest   — final Markdown digest
    - error    — something went wrong
    - done     — agent finished
    """

    async def event_generator():
        try:
            async for evt in run_research_agent(topic.strip()):
                event_type = evt.get("event", "message")
                data = evt.get("data", {})
                payload = json.dumps(data, default=str)
                yield f"event: {event_type}\ndata: {payload}\n\n"
        except Exception as exc:
            logger.error("Research agent error: %s", exc)
            error_payload = json.dumps({"message": f"Agent error: {exc}"})
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

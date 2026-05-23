"""
MCP-powered Research Agent using LangGraph.

Replaces the hand-written arXiv HTTP calls from Project 10 with MCP server
tools, while producing the **exact same** SSE event stream so the frontend
and system prompt remain completely unchanged.

Architecture
────────────
LangGraph StateGraph with five sequential nodes:

  plan → search → rank → analyze → digest

Each node captures SSE events in ``step_events`` which the outer async
generator yields to the caller.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.mcp_arxiv_client import (
    create_arxiv_mcp_session,
    mcp_download_paper,
    mcp_read_paper,
    mcp_search_papers,
)

logger = logging.getLogger(__name__)

MAX_PAPERS_TO_ANALYZE = 8


# ---------------------------------------------------------------------------
# SSE event helper (same shape as Project 10)
# ---------------------------------------------------------------------------

def _event(event_type: str, data: Any) -> dict[str, Any]:
    return {"event": event_type, "data": data}


# ---------------------------------------------------------------------------
# LangGraph state schema
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    topic: str
    search_queries: list[str]
    papers: list[dict[str, Any]]
    paper_analyses: list[dict[str, Any]]
    digest: str
    # Per-node SSE events; extracted by the streaming runner
    step_events: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# LLM helpers (identical to Project 10)
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.litellm_model,
        openai_api_key=settings.litellm_virtual_key,
        openai_api_base=f"{settings.litellm_proxy_url}/v1",
        temperature=0.2,
        default_headers={
            "x-litellm-user": settings.litellm_user_id,
            "x-litellm-department": settings.litellm_department,
            "x-litellm-environment": settings.litellm_environment,
        },
    )


async def _llm_json(llm: ChatOpenAI, system: str, user: str) -> Any:
    """Call the LLM and parse the response as JSON."""
    resp = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    raw = resp.content.strip()
    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith(("json", "JSON")):
                inner = inner.split("\n", 1)[1] if "\n" in inner else inner
            raw = inner.strip()
    return json.loads(raw)


async def _llm_text(llm: ChatOpenAI, system: str, user: str) -> str:
    """Call the LLM and return plain text."""
    resp = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return resp.content.strip()


# ---------------------------------------------------------------------------
# Graph builder — nodes are closures over mcp_session & llm
# ---------------------------------------------------------------------------

def _build_research_graph(mcp_session: Any, llm: ChatOpenAI):
    """Build and compile the LangGraph research workflow."""

    # ── Node 1: Plan search queries ─────────────────────────────────
    async def plan_searches(state: ResearchState) -> dict:
        topic = state["topic"]
        events: list[dict] = [
            _event("status", {
                "step": "planning",
                "message": f"Planning research strategy for: {topic}",
            }),
        ]

        system = (
            "You are a research assistant. Given a research topic, generate "
            "2-4 specific search queries optimized for arXiv's search engine. "
            "Include varied angles (techniques, applications, surveys).\n"
            "Return ONLY a JSON array of query strings. Example:\n"
            '["transformer architecture improvements 2024", '
            '"attention mechanism efficiency"]'
        )
        try:
            result = await _llm_json(llm, system, f"Research topic: {topic}")
            queries = (
                [str(q) for q in result[:4]]
                if isinstance(result, list)
                else [topic]
            )
        except Exception as exc:
            logger.warning("Query planning failed: %s", exc)
            queries = [topic]

        events.append(_event("queries", {"queries": queries}))
        return {"search_queries": queries, "step_events": events}

    # ── Node 2: Search via MCP ──────────────────────────────────────
    async def search_papers(state: ResearchState) -> dict:
        events: list[dict] = []
        all_papers: list[dict] = []
        seen_ids: set[str] = set()

        for query in state["search_queries"]:
            events.append(
                _event("status", {
                    "step": "searching",
                    "message": f"Searching arXiv via MCP: {query}",
                })
            )
            try:
                raw_text = await mcp_search_papers(
                    mcp_session, query, max_results=10,
                )

                # Have the LLM parse MCP text into structured paper dicts
                parse_system = (
                    "You are a data parser. Extract paper information from "
                    "the following arXiv search results.\n"
                    "Return ONLY a JSON array of objects with keys:\n"
                    '- "paper_id": arXiv ID (e.g. "2401.12345")\n'
                    '- "title": paper title\n'
                    '- "authors": array of author names\n'
                    '- "abstract": the abstract text\n'
                    '- "published": date string (YYYY-MM-DD if available)\n'
                    '- "updated": date string (YYYY-MM-DD if available)\n'
                    '- "categories": array of arXiv categories\n'
                    "Use empty string / empty array for unknown fields.\n"
                    "If no papers are found return []."
                )
                parsed = await _llm_json(
                    llm, parse_system, f"Search results:\n{raw_text}"
                )

                if isinstance(parsed, list):
                    for p in parsed:
                        pid = str(p.get("paper_id", "")).strip()
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            all_papers.append({
                                "paper_id": pid,
                                "title": p.get("title", ""),
                                "authors": p.get("authors", []),
                                "abstract": p.get("abstract", ""),
                                "published": p.get("published", ""),
                                "updated": p.get("updated", ""),
                                "pdf_url": f"https://arxiv.org/pdf/{pid}",
                                "arxiv_url": f"https://arxiv.org/abs/{pid}",
                                "categories": p.get("categories", []),
                                "relevance_score": 0.0,
                            })
            except Exception as exc:
                logger.warning("MCP search failed for '%s': %s", query, exc)
                events.append(
                    _event("status", {
                        "step": "searching",
                        "message": f"Search failed for: {query} — {exc}",
                    })
                )

        if not all_papers:
            events.append(
                _event("error", {
                    "message": "No papers found on arXiv for this topic. "
                               "Try a different query.",
                })
            )

        return {"papers": all_papers, "step_events": events}

    # ── Node 3: Rank papers ─────────────────────────────────────────
    async def rank_papers(state: ResearchState) -> dict:
        papers = state["papers"]
        events: list[dict] = [
            _event("status", {
                "step": "ranking",
                "message": f"Ranking {len(papers)} papers by relevance…",
            }),
        ]

        if not papers:
            return {"papers": [], "step_events": events}

        paper_list = "\n".join(
            f"[{i}] {p['title']} — {p.get('abstract', '')[:200]}…"
            for i, p in enumerate(papers)
        )

        system = (
            "You are a research paper relevance ranker. Given a topic and "
            "a list of papers, score each paper 0-10 on relevance. Return "
            "ONLY a JSON array of objects with "
            '"index" (int) and "score" (float). '
            'Example: [{"index": 0, "score": 9.5}]'
        )
        try:
            scores = await _llm_json(
                llm, system,
                f"Topic: {state['topic']}\n\nPapers:\n{paper_list}",
            )
            if isinstance(scores, list):
                score_map = {
                    item["index"]: float(item["score"])
                    for item in scores
                    if "index" in item and "score" in item
                }
                for i, p in enumerate(papers):
                    p["relevance_score"] = score_map.get(i, 5.0)
        except Exception as exc:
            logger.warning("Ranking failed: %s", exc)

        papers.sort(key=lambda p: p.get("relevance_score", 0), reverse=True)
        top_papers = papers[:MAX_PAPERS_TO_ANALYZE]
        events.append(_event("papers", top_papers))
        return {"papers": top_papers, "step_events": events}

    # ── Node 4: Analyze papers (with MCP full-text) ─────────────────
    async def analyze_papers(state: ResearchState) -> dict:
        papers = state["papers"]
        events: list[dict] = []
        analyses: list[dict] = []

        for i, paper in enumerate(papers):
            events.append(
                _event("status", {
                    "step": "analyzing",
                    "message": (
                        f"Analyzing ({i + 1}/{len(papers)}): "
                        f"{paper['title']}"
                    ),
                })
            )

            # Try fetching full text via MCP (download → read)
            full_text = ""
            try:
                await mcp_download_paper(mcp_session, paper["paper_id"])
                full_text = await mcp_read_paper(mcp_session, paper["paper_id"])
                if len(full_text) > 4000:
                    full_text = full_text[:4000] + "\n…[truncated]"
            except Exception as exc:
                logger.debug(
                    "Could not fetch full text for %s via MCP: %s",
                    paper["paper_id"], exc,
                )

            paper_text = (
                f"Title: {paper['title']}\n"
                f"Authors: {', '.join(paper.get('authors', [])[:5])}\n"
                f"Published: {paper.get('published', 'N/A')}\n"
                f"Abstract: {paper.get('abstract', '')}\n"
            )
            if full_text:
                paper_text += (
                    f"\nFull Paper Content (excerpt):\n{full_text}"
                )

            system = (
                "You are a research analyst. Summarize this paper in the "
                "context of the given topic. Return ONLY a JSON object "
                "with keys:\n"
                '- "summary": concise 2-3 sentence summary\n'
                '- "key_findings": array of 2-4 key findings\n'
                '- "methodology": brief methodology description\n'
                '- "relevance": "high", "medium", or "low"\n'
                '- "limitations": 1-2 sentence limitations (if apparent)'
            )

            try:
                result = await _llm_json(
                    llm, system,
                    f"Topic: {state['topic']}\n\nPaper:\n{paper_text}",
                )
                if isinstance(result, dict):
                    result["paper_id"] = paper["paper_id"]
                    result["title"] = paper["title"]
                    result["authors"] = paper.get("authors", [])
                    result["published"] = paper.get("published", "")
                    result["arxiv_url"] = paper.get("arxiv_url", "")
                    result["pdf_url"] = paper.get("pdf_url", "")
                    analyses.append(result)
                    events.append(_event("paper_analysis", result))
                    continue
            except Exception as exc:
                logger.warning(
                    "Analysis failed for '%s': %s", paper["title"], exc,
                )

            # Fallback
            fallback = {
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "authors": paper.get("authors", []),
                "published": paper.get("published", ""),
                "arxiv_url": paper.get("arxiv_url", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "summary": paper.get("abstract", "")[:300],
                "key_findings": [],
                "methodology": "",
                "relevance": "medium",
                "limitations": "",
            }
            analyses.append(fallback)
            events.append(_event("paper_analysis", fallback))

        return {"paper_analyses": analyses, "step_events": events}

    # ── Node 5: Generate final digest ───────────────────────────────
    async def generate_digest(state: ResearchState) -> dict:
        events: list[dict] = [
            _event("status", {
                "step": "synthesizing",
                "message": "Generating research digest…",
            }),
        ]

        analyses_text = ""
        for a in state["paper_analyses"]:
            analyses_text += (
                f"### {a['title']}\n"
                f"- Authors: {', '.join(a.get('authors', [])[:3])}\n"
                f"- Published: {a.get('published', 'N/A')}\n"
                f"- Summary: {a.get('summary', '')}\n"
                f"- Key findings: {', '.join(a.get('key_findings', []))}\n"
                f"- Methodology: {a.get('methodology', '')}\n"
                f"- Relevance: {a.get('relevance', '')}\n"
                f"- Limitations: {a.get('limitations', '')}\n"
                f"- Link: {a.get('arxiv_url', '')}\n\n"
            )

        system = (
            "You are a senior research analyst. Produce a comprehensive, "
            "well-structured research digest in Markdown based on the "
            "analyzed papers.\n\n"
            "FORMAT (use these exact headings):\n"
            "## Research Digest: <topic>\n\n"
            "### Executive Summary\n"
            "A 3-5 sentence overview.\n\n"
            "### Key Findings\n"
            "Numbered list of the most important findings.\n\n"
            "### Emerging Trends\n"
            "Bullet list of research trends.\n\n"
            "### Notable Papers\n"
            "For each important paper: title, one-line summary, arXiv link.\n\n"
            "### Limitations & Gaps\n"
            "What's missing or under-explored.\n\n"
            "### Future Directions\n"
            "Suggested areas for further research.\n\n"
            "### References\n"
            "Numbered list with arXiv links.\n\n"
            "RULES:\n"
            "- Only cite papers from the provided analyses — NEVER invent.\n"
            "- Include the arXiv URL for every paper you mention.\n"
            "- Be specific and technical, not generic.\n"
            "- Use the actual paper titles and findings."
        )

        digest_md = await _llm_text(
            llm, system,
            f"Topic: {state['topic']}\n\nAnalyzed Papers:\n{analyses_text}",
        )
        events.append(_event("digest", {"content": digest_md}))
        return {"digest": digest_md, "step_events": events}

    # ── Assemble graph ──────────────────────────────────────────────
    graph = StateGraph(ResearchState)
    graph.add_node("plan", plan_searches)
    graph.add_node("search", search_papers)
    graph.add_node("rank", rank_papers)
    graph.add_node("analyze", analyze_papers)
    graph.add_node("digest", generate_digest)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "search")
    graph.add_edge("search", "rank")
    graph.add_edge("rank", "analyze")
    graph.add_edge("analyze", "digest")
    graph.add_edge("digest", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public entry point — yields SSE events (drop-in replacement)
# ---------------------------------------------------------------------------

async def run_mcp_research_agent(
    topic: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Autonomous research agent powered by the arxiv-mcp-server (MCP) and
    orchestrated by LangGraph.

    Yields SSE-compatible event dicts **identical** to the original
    ``run_research_agent`` from Project 10, so the frontend and system
    prompt require zero changes.
    """
    llm = _get_llm()

    async with create_arxiv_mcp_session() as mcp_session:
        agent = _build_research_graph(mcp_session, llm)

        initial_state: ResearchState = {
            "topic": topic,
            "search_queries": [],
            "papers": [],
            "paper_analyses": [],
            "digest": "",
            "step_events": [],
        }

        papers_found = 0
        papers_analyzed = 0

        async for chunk in agent.astream(
            initial_state, stream_mode="updates"
        ):
            for _node_name, node_output in chunk.items():
                for evt in node_output.get("step_events", []):
                    yield evt

                if "papers" in node_output:
                    papers_found = len(node_output["papers"])
                if "paper_analyses" in node_output:
                    papers_analyzed = len(node_output["paper_analyses"])

        yield _event("done", {
            "papers_found": papers_found,
            "papers_analyzed": papers_analyzed,
        })

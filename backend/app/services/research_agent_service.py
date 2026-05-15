"""
Autonomous Research Agent that searches arXiv, analyzes papers, and
produces a structured research digest — streaming events to the caller.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.services.arxiv_service import ArxivPaper, MAX_RESULTS_PER_QUERY, search_arxiv

logger = logging.getLogger(__name__)

MAX_PAPERS_TO_ANALYZE = 8
MAX_SEARCH_ROUNDS = 2


# ---------------------------------------------------------------------------
# SSE event helpers
# ---------------------------------------------------------------------------

def _event(event_type: str, data: Any) -> dict[str, Any]:
    return {"event": event_type, "data": data}


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class ResearchState:
    topic: str
    search_queries: list[str] = field(default_factory=list)
    papers: list[ArxivPaper] = field(default_factory=list)
    paper_analyses: list[dict[str, Any]] = field(default_factory=list)
    digest: str | None = None


# ---------------------------------------------------------------------------
# LLM helper
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
    resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
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
    resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content.strip()


# ---------------------------------------------------------------------------
# Agent steps
# ---------------------------------------------------------------------------

async def _plan_searches(llm: ChatOpenAI, topic: str) -> list[str]:
    """Generate arXiv search queries for the topic."""
    system = (
        "You are a research assistant. Given a research topic, generate 2-4 specific "
        "search queries optimized for arXiv's search engine. Include varied angles "
        "(techniques, applications, surveys).\n"
        "Return ONLY a JSON array of query strings. Example:\n"
        '["transformer architecture improvements 2024", "attention mechanism efficiency"]'
    )
    try:
        result = await _llm_json(llm, system, f"Research topic: {topic}")
        if isinstance(result, list):
            return [str(q) for q in result[:4]]
    except Exception as exc:
        logger.warning("Query planning failed, using topic as query: %s", exc)
    return [topic]


async def _rank_papers(
    llm: ChatOpenAI, papers: list[ArxivPaper], topic: str,
) -> list[ArxivPaper]:
    """Rank papers by relevance using the LLM."""
    if not papers:
        return []

    paper_list = "\n".join(
        f"[{i}] {p.title} — {p.abstract[:200]}…"
        for i, p in enumerate(papers)
    )

    system = (
        "You are a research paper relevance ranker. Given a topic and a list of papers, "
        "score each paper 0-10 on relevance. Return ONLY a JSON array of objects with "
        '"index" (int) and "score" (float). Example: [{"index": 0, "score": 9.5}]'
    )

    try:
        scores = await _llm_json(
            llm, system,
            f"Topic: {topic}\n\nPapers:\n{paper_list}",
        )
        if isinstance(scores, list):
            score_map = {item["index"]: float(item["score"]) for item in scores if "index" in item and "score" in item}
            for i, p in enumerate(papers):
                p.relevance_score = score_map.get(i, 5.0)
    except Exception as exc:
        logger.warning("Paper ranking failed: %s", exc)

    papers.sort(key=lambda p: p.relevance_score, reverse=True)
    return papers


async def _analyze_paper(llm: ChatOpenAI, paper: ArxivPaper, topic: str) -> dict[str, Any]:
    """Summarize a single paper in the context of the research topic."""
    system = (
        "You are a research analyst. Summarize this paper in the context of the given topic. "
        "Return ONLY a JSON object with keys:\n"
        '- "summary": concise 2-3 sentence summary\n'
        '- "key_findings": array of 2-4 key findings\n'
        '- "methodology": brief methodology description\n'
        '- "relevance": "high", "medium", or "low"\n'
        '- "limitations": 1-2 sentence limitations (if apparent from abstract)'
    )

    paper_text = (
        f"Title: {paper.title}\n"
        f"Authors: {', '.join(paper.authors[:5])}\n"
        f"Published: {paper.published}\n"
        f"Abstract: {paper.abstract}"
    )

    try:
        result = await _llm_json(llm, system, f"Topic: {topic}\n\nPaper:\n{paper_text}")
        if isinstance(result, dict):
            result["paper_id"] = paper.paper_id
            result["title"] = paper.title
            result["authors"] = paper.authors
            result["published"] = paper.published
            result["arxiv_url"] = paper.arxiv_url
            result["pdf_url"] = paper.pdf_url
            return result
    except Exception as exc:
        logger.warning("Paper analysis failed for '%s': %s", paper.title, exc)

    # Fallback
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "authors": paper.authors,
        "published": paper.published,
        "arxiv_url": paper.arxiv_url,
        "pdf_url": paper.pdf_url,
        "summary": paper.abstract[:300],
        "key_findings": [],
        "methodology": "",
        "relevance": "medium",
        "limitations": "",
    }


async def _generate_digest(
    llm: ChatOpenAI, topic: str, analyses: list[dict[str, Any]],
) -> str:
    """Generate the final structured research digest in Markdown."""
    analyses_text = ""
    for a in analyses:
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
        "You are a senior research analyst. Produce a comprehensive, well-structured "
        "research digest in Markdown based on the analyzed papers.\n\n"
        "FORMAT (use these exact headings):\n"
        "## Research Digest: <topic>\n\n"
        "### Executive Summary\n"
        "A 3-5 sentence overview.\n\n"
        "### Key Findings\n"
        "Numbered list of the most important findings across all papers.\n\n"
        "### Emerging Trends\n"
        "Bullet list of research trends.\n\n"
        "### Notable Papers\n"
        "For each important paper: title, one-line summary, and arXiv link.\n\n"
        "### Limitations & Gaps\n"
        "What's missing or under-explored.\n\n"
        "### Future Directions\n"
        "Suggested areas for further research.\n\n"
        "### References\n"
        "Numbered list with arXiv links.\n\n"
        "RULES:\n"
        "- Only cite papers from the provided analyses — NEVER invent citations.\n"
        "- Include the arXiv URL for every paper you mention.\n"
        "- Be specific and technical, not generic.\n"
        "- Use the actual paper titles and findings."
    )

    return await _llm_text(llm, system, f"Topic: {topic}\n\nAnalyzed Papers:\n{analyses_text}")


# ---------------------------------------------------------------------------
# Main agent loop — yields SSE events
# ---------------------------------------------------------------------------

async def run_research_agent(topic: str) -> AsyncGenerator[dict[str, Any], None]:
    """
    Autonomous research agent that searches arXiv, analyzes papers, and
    generates a structured digest. Yields SSE-compatible event dicts.
    """
    llm = _get_llm()
    state = ResearchState(topic=topic)

    # ── Step 1: Plan search queries ──
    yield _event("status", {"step": "planning", "message": f"Planning research strategy for: {topic}"})

    state.search_queries = await _plan_searches(llm, topic)
    yield _event("queries", {"queries": state.search_queries})

    # ── Step 2: Search arXiv ──
    seen_ids: set[str] = set()

    for query in state.search_queries:
        yield _event("status", {"step": "searching", "message": f"Searching arXiv: {query}"})

        papers = await search_arxiv(query, max_results=MAX_RESULTS_PER_QUERY, sort_by="relevance")

        for p in papers:
            if p.paper_id not in seen_ids:
                seen_ids.add(p.paper_id)
                state.papers.append(p)

    if not state.papers:
        yield _event("error", {"message": "No papers found on arXiv for this topic. Try a different query."})
        yield _event("done", {})
        return

    # ── Step 3: Rank papers ──
    yield _event("status", {"step": "ranking", "message": f"Ranking {len(state.papers)} papers by relevance…"})

    state.papers = await _rank_papers(llm, state.papers, topic)

    # Send top papers to the frontend
    top_papers = state.papers[:MAX_PAPERS_TO_ANALYZE]
    yield _event("papers", [p.to_dict() for p in top_papers])

    # ── Step 4: Analyze top papers ──
    for i, paper in enumerate(top_papers):
        yield _event("status", {
            "step": "analyzing",
            "message": f"Analyzing ({i + 1}/{len(top_papers)}): {paper.title}",
        })

        analysis = await _analyze_paper(llm, paper, topic)
        state.paper_analyses.append(analysis)

        yield _event("paper_analysis", analysis)

    # ── Step 5: Generate final digest ──
    yield _event("status", {"step": "synthesizing", "message": "Generating research digest…"})

    state.digest = await _generate_digest(llm, topic, state.paper_analyses)
    yield _event("digest", {"content": state.digest})

    yield _event("done", {
        "papers_found": len(state.papers),
        "papers_analyzed": len(state.paper_analyses),
    })

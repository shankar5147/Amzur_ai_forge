"""Service for searching arXiv and fetching paper metadata."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
MAX_RESULTS_PER_QUERY = 10
MIN_REQUEST_INTERVAL = 3.0  # arXiv asks for ≥3 s between requests

_last_request_time: float = 0.0


@dataclass
class ArxivPaper:
    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    updated: str
    pdf_url: str
    arxiv_url: str
    categories: list[str]
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published": self.published,
            "updated": self.updated,
            "pdf_url": self.pdf_url,
            "arxiv_url": self.arxiv_url,
            "categories": self.categories,
            "relevance_score": self.relevance_score,
        }


def _parse_atom_feed(xml_text: str) -> list[ArxivPaper]:
    """Parse arXiv Atom XML feed into ArxivPaper objects (no lxml dependency)."""
    papers: list[ArxivPaper] = []

    # Split entries
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)

    for entry in entries:
        # Extract fields with simple regex
        paper_id_match = re.search(r"<id>(.*?)</id>", entry)
        title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        summary_match = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        published_match = re.search(r"<published>(.*?)</published>", entry)
        updated_match = re.search(r"<updated>(.*?)</updated>", entry)

        if not paper_id_match or not title_match:
            continue

        raw_id = paper_id_match.group(1).strip()
        # Extract arXiv ID from URL like http://arxiv.org/abs/2401.12345v1
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1] if "/abs/" in raw_id else raw_id

        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        abstract = re.sub(r"\s+", " ", summary_match.group(1)).strip() if summary_match else ""
        published = published_match.group(1).strip() if published_match else ""
        updated = updated_match.group(1).strip() if updated_match else ""

        # Authors
        authors = [
            re.sub(r"\s+", " ", name.strip())
            for name in re.findall(r"<name>(.*?)</name>", entry)
        ]

        # Categories
        categories = re.findall(r'<category[^>]*term="([^"]*)"', entry)

        # PDF link
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"

        papers.append(ArxivPaper(
            paper_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            published=published[:10],  # YYYY-MM-DD
            updated=updated[:10],
            pdf_url=pdf_url,
            arxiv_url=arxiv_url,
            categories=categories,
        ))

    return papers


async def _rate_limited_wait() -> None:
    """Respect arXiv's rate-limit policy."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


async def search_arxiv(
    query: str,
    max_results: int = MAX_RESULTS_PER_QUERY,
    sort_by: str = "relevance",
    sort_order: str = "descending",
) -> list[ArxivPaper]:
    """
    Search arXiv for papers matching the query.

    Args:
        query: Search query string (supports arXiv query syntax).
        max_results: Maximum number of results to return.
        sort_by: One of "relevance", "lastUpdatedDate", "submittedDate".
        sort_order: "ascending" or "descending".

    Returns:
        List of ArxivPaper objects.
    """
    await _rate_limited_wait()

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(max_results, 30),  # cap at 30
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(ARXIV_API_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("arXiv API request failed: %s", exc)
        return []

    papers = _parse_atom_feed(resp.text)
    logger.info("arXiv search for '%s' returned %d papers", query, len(papers))
    return papers


async def fetch_paper_abstract(paper_id: str) -> str | None:
    """Fetch a single paper's abstract by ID."""
    await _rate_limited_wait()

    params = {"id_list": paper_id, "max_results": 1}

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(ARXIV_API_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch paper %s: %s", paper_id, exc)
        return None

    papers = _parse_atom_feed(resp.text)
    return papers[0].abstract if papers else None

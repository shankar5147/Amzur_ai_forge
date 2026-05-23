"""
MCP client for communicating with the arxiv-mcp-server.

Provides an async context manager that starts the MCP server subprocess
and exposes helper functions for each tool (search_papers, download_paper,
read_paper, list_papers).
"""

from __future__ import annotations

import logging
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

# Default local storage for downloaded papers
_DEFAULT_STORAGE = Path.home() / ".arxiv-mcp-server" / "papers"


def _find_server_command() -> tuple[str, list[str]]:
    """Locate the arxiv-mcp-server executable on the system."""
    # 1) Check in the same venv Scripts directory as the running Python
    venv_scripts = Path(sys.executable).parent
    venv_exe = venv_scripts / "arxiv-mcp-server.exe"
    if venv_exe.exists():
        return str(venv_exe), []
    venv_exe_nix = venv_scripts / "arxiv-mcp-server"
    if venv_exe_nix.exists():
        return str(venv_exe_nix), []
    # 2) Check PATH
    if shutil.which("arxiv-mcp-server"):
        return "arxiv-mcp-server", []
    if shutil.which("uvx"):
        return "uvx", ["arxiv-mcp-server"]
    # 3) Fallback to python -m
    return sys.executable, ["-m", "arxiv_mcp_server"]


# ------------------------------------------------------------------
# Session lifecycle
# ------------------------------------------------------------------

@asynccontextmanager
async def create_arxiv_mcp_session(
    storage_path: str | Path | None = None,
):
    """
    Start the arxiv-mcp-server over stdio and yield a ready
    ``ClientSession``.  The subprocess is cleaned up on exit.
    """
    storage = str(storage_path or _DEFAULT_STORAGE)
    Path(storage).mkdir(parents=True, exist_ok=True)

    cmd, base_args = _find_server_command()
    args = base_args + ["--storage-path", storage]

    server_params = StdioServerParameters(command=cmd, args=args)
    logger.info("Starting arxiv-mcp-server: %s %s", cmd, " ".join(args))

    async with stdio_client(server_params) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            # Log available tools for debugging
            tools_resp = await session.list_tools()
            tool_names = [t.name for t in tools_resp.tools]
            logger.info("MCP session ready — tools: %s", tool_names)
            yield session


# ------------------------------------------------------------------
# Tool helpers
# ------------------------------------------------------------------

def _extract_text(result: Any) -> str:
    """Pull all text blocks out of an MCP ``CallToolResult``."""
    parts: list[str] = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


async def mcp_search_papers(
    session: ClientSession,
    query: str,
    max_results: int = 10,
    **kwargs: Any,
) -> str:
    """Search arXiv papers via the MCP server. Returns raw text."""
    arguments: dict[str, Any] = {"query": query, "max_results": max_results}
    arguments.update(kwargs)
    result = await session.call_tool("search_papers", arguments)
    if result.isError:
        raise RuntimeError(
            f"MCP search_papers error: {_extract_text(result)}"
        )
    return _extract_text(result)


async def mcp_download_paper(session: ClientSession, paper_id: str) -> str:
    """Download a paper to local storage via the MCP server."""
    result = await session.call_tool("download_paper", {"paper_id": paper_id})
    if result.isError:
        raise RuntimeError(
            f"MCP download_paper error: {_extract_text(result)}"
        )
    return _extract_text(result)


async def mcp_read_paper(session: ClientSession, paper_id: str) -> str:
    """Read the full text of a previously downloaded paper."""
    result = await session.call_tool("read_paper", {"paper_id": paper_id})
    if result.isError:
        raise RuntimeError(
            f"MCP read_paper error: {_extract_text(result)}"
        )
    return _extract_text(result)


async def mcp_list_papers(session: ClientSession) -> str:
    """List papers that have been downloaded locally."""
    result = await session.call_tool("list_papers", {})
    return _extract_text(result)

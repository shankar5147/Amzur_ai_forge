"""LangChain Pandas DataFrame agent service for natural-language data analysis."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class DataFrameAgentError(Exception):
    pass


_SYSTEM_PROMPT_TEMPLATE = """You are a data analyst assistant. You have access to a Pandas DataFrame named `df`.

DataFrame info:
- Shape: {shape}
- Columns: {columns}
- Data types:
{dtypes}
- First few rows:
{head}

RULES:
1. Answer the user's question by writing a short Python expression using `df` and Pandas.
2. Return ONLY a JSON object with two keys:
   - "code": a single Python expression (NOT multi-line statements) that computes the answer using `df`.
   - "explanation": a concise natural-language description of what the code does.
3. The code must use ONLY the `df` variable and standard Pandas/Python built-ins.
4. Do NOT import anything, define functions, use exec/eval/compile/os/sys/subprocess, or access the filesystem.
5. Keep the code simple: aggregations, filters, groupby, value_counts, describe, etc.
6. If the question cannot be answered from the data, set "code" to null and explain why.
7. Always use the exact column names shown above.

Example output:
{{"code": "df['sales'].max()", "explanation": "Find the maximum value in the sales column."}}
"""

# Allowed built-in names for safe eval
_SAFE_BUILTINS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "frozenset", "int", "isinstance", "len", "list", "map", "max", "min",
    "range", "round", "set", "sorted", "str", "sum", "tuple", "type", "zip",
}

# Blocked patterns for safe eval (word-boundary matching to avoid false positives)
_BLOCKED_PATTERNS = re.compile(
    r"\b(import|exec|eval|compile|open|subprocess|shutil|pathlib"
    r"|globals|locals|getattr|setattr|delattr|breakpoint|exit|quit)\b"
    r"|__|(?<!\w)(os|sys)\.",
    re.IGNORECASE,
)


def _validate_code(code: str) -> None:
    """Check that generated code doesn't contain dangerous operations."""
    match = _BLOCKED_PATTERNS.search(code)
    if match:
        raise DataFrameAgentError(
            f"Generated code contains blocked operation: '{match.group()}'"
        )


def _safe_eval(code: str, df: pd.DataFrame) -> Any:
    """Evaluate a Pandas expression in a restricted namespace."""
    _validate_code(code)

    import builtins as _builtins
    import numpy as np

    # Build a restricted builtins dict with only safe names
    restricted_builtins = {name: getattr(_builtins, name) for name in _SAFE_BUILTINS if hasattr(_builtins, name)}
    # Pandas/numpy internals need a few more to work properly
    for extra in ("True", "False", "None", "isinstance", "hasattr", "TypeError", "ValueError", "KeyError",
                  "IndexError", "AttributeError", "StopIteration", "NotImplementedError", "object"):
        if hasattr(_builtins, extra):
            restricted_builtins[extra] = getattr(_builtins, extra)

    safe_globals: dict[str, Any] = {
        "__builtins__": restricted_builtins,
        "pd": pd,
        "np": np,
    }
    safe_locals: dict[str, Any] = {"df": df}

    try:
        result = eval(code, safe_globals, safe_locals)  # noqa: S307
    except Exception as exc:
        raise DataFrameAgentError(f"Code execution error: {exc}") from exc

    return result


def _format_result(result: Any) -> str:
    """Convert eval result to a human-readable Markdown string."""
    if result is None:
        return "No result."
    if isinstance(result, pd.DataFrame):
        df_out = result.head(100) if len(result) > 100 else result
        md = _dataframe_to_markdown(df_out)
        if len(result) > 100:
            md += f"\n\n*… showing 100 of {len(result)} rows*"
        return md
    if isinstance(result, pd.Series):
        # Convert Series to a two-column DataFrame for table rendering
        s_out = result.head(100) if len(result) > 100 else result
        df_out = s_out.reset_index()
        df_out.columns = pd.Index([str(s_out.index.name or "index"), str(s_out.name or "value")])
        md = _dataframe_to_markdown(df_out)
        if len(result) > 100:
            md += f"\n\n*… showing 100 of {len(result)} entries*"
        return md
    return str(result)


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a Markdown table string."""
    cols = list(df.columns)
    # Header row
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"
    # Data rows
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            val = row[c]
            # Convert to string, replace pipe chars to avoid breaking the table
            cell = str(val) if pd.notna(val) else ""
            cell = cell.replace("|", "\\|").replace("\n", " ")
            cells.append(cell)
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, separator] + rows)


class DataFrameAgentService:
    """Uses an LLM to translate natural-language questions into Pandas operations."""

    def __init__(self) -> None:
        if not settings.litellm_virtual_key:
            raise DataFrameAgentError("Missing LITELLM_VIRTUAL_KEY.")

        self._llm = ChatOpenAI(
            model=settings.litellm_model,
            openai_api_key=settings.litellm_virtual_key,
            openai_api_base=f"{settings.litellm_proxy_url}/v1",
            temperature=0.1,
            default_headers={
                "x-litellm-user": settings.litellm_user_id,
                "x-litellm-department": settings.litellm_department,
                "x-litellm-environment": settings.litellm_environment,
            },
        )

    async def ask(self, df: pd.DataFrame, question: str) -> dict[str, str]:
        """
        Ask a natural-language question about a DataFrame.

        Returns {"answer": "...", "code": "..."}.
        """
        # Build context from the DataFrame
        head_str = df.head(5).to_string(index=False)
        dtypes_str = "\n".join(f"  {col}: {dtype}" for col, dtype in df.dtypes.items())
        columns_str = ", ".join(df.columns)

        # Build system prompt as a plain string (no template parsing)
        system_content = _SYSTEM_PROMPT_TEMPLATE.format(
            shape=df.shape,
            columns=columns_str,
            dtypes=dtypes_str,
            head=head_str,
        )

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=question),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            raw = response.content.strip()
            logger.info("LLM raw response (first 500 chars): %s", raw[:500])
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise DataFrameAgentError(f"AI analysis failed: {exc}") from exc

        # Strip markdown code fences if present (e.g. ```json ... ```)
        cleaned = raw
        if "```" in cleaned:
            # Extract content between first ``` and last ```
            parts = cleaned.split("```")
            if len(parts) >= 3:
                inner = parts[1]
                # Remove optional language tag on first line (e.g. "json")
                if inner.startswith(("json", "python", "JSON")):
                    inner = inner.split("\n", 1)[1] if "\n" in inner else inner
                cleaned = inner.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # If the LLM didn't return JSON, treat the whole response as the answer
            logger.warning("LLM returned non-JSON response: %s", raw[:200])
            return {"answer": raw, "code": None}

        code = parsed.get("code") or None
        explanation = parsed.get("explanation", "")

        # If LLM returned actual code, execute it safely
        if code and str(code).strip().lower() not in ("none", "null", ""):
            code = str(code).strip()
            try:
                result = _safe_eval(code, df)
                formatted = _format_result(result)
                answer = f"{explanation}\n\n**Result:**\n{formatted}"
            except DataFrameAgentError as exc:
                logger.warning("Code execution failed for code: %s — %s", code, exc)
                answer = f"{explanation}\n\n(Code execution failed: {exc})"
        else:
            code = None
            answer = explanation or "This question cannot be answered from the available data."

        return {"answer": answer, "code": code}

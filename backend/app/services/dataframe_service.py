"""Service for loading, cleaning, and managing Pandas DataFrames from CSV/XLSX files."""

from __future__ import annotations

import logging
import re
import uuid
from io import BytesIO
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Maximum upload size: 15 MB
MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_PREVIEW_ROWS = 50


class DataFrameServiceError(Exception):
    pass


class DataFrameSessionStore:
    """In-memory store for active DataFrame sessions (per-user)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def put(self, session_id: str, data: dict[str, Any]) -> None:
        self._sessions[session_id] = data

    def get(self, session_id: str) -> dict[str, Any] | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        results = []
        for sid, data in self._sessions.items():
            df: pd.DataFrame = data["df"]
            results.append(
                {
                    "session_id": sid,
                    "file_name": data.get("file_name", "unknown"),
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                }
            )
        return results


# Global session store
session_store = DataFrameSessionStore()


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names: lowercase, strip, replace spaces/special chars with underscores."""
    df.columns = [
        re.sub(r"[^a-z0-9_]", "_", str(col).strip().lower()).strip("_")
        for col in df.columns
    ]
    # Deduplicate column names
    seen: dict[str, int] = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = pd.Index(new_cols)
    return df


def _safe_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame for safe querying."""
    df = _clean_column_names(df)
    # Drop fully empty rows and columns
    df = df.dropna(how="all").dropna(axis=1, how="all")
    # Fill remaining NaNs for string columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].fillna("")
    return df


def validate_file(file_name: str, file_size: int) -> None:
    """Validate file extension and size."""
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise DataFrameServiceError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    if file_size > MAX_FILE_SIZE:
        raise DataFrameServiceError(
            f"File too large ({file_size / (1024*1024):.1f} MB). Maximum: {MAX_FILE_SIZE / (1024*1024):.0f} MB."
        )


def load_dataframe_from_bytes(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Parse CSV or Excel bytes into a cleaned Pandas DataFrame."""
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    buf = BytesIO(file_bytes)

    try:
        if ext == ".csv":
            df = pd.read_csv(buf)
        elif ext in {".xlsx", ".xls"}:
            df = pd.read_excel(buf, engine="openpyxl")
        else:
            raise DataFrameServiceError(f"Cannot parse file type: {ext}")
    except DataFrameServiceError:
        raise
    except Exception as exc:
        raise DataFrameServiceError(f"Failed to parse file: {exc}") from exc

    if df.empty:
        raise DataFrameServiceError("The uploaded file contains no data.")

    return _safe_clean(df)


def create_session(df: pd.DataFrame, file_name: str) -> str:
    """Store a DataFrame in the session store, return session ID."""
    session_id = str(uuid.uuid4())
    session_store.put(session_id, {"df": df, "file_name": file_name})
    logger.info("Created data session %s for file '%s' (%d rows, %d cols)", session_id, file_name, len(df), len(df.columns))
    return session_id


def get_session_df(session_id: str) -> pd.DataFrame:
    """Retrieve a DataFrame by session ID."""
    session = session_store.get(session_id)
    if session is None:
        raise DataFrameServiceError(f"Session '{session_id}' not found. Please upload a file first.")
    return session["df"]


def get_preview(df: pd.DataFrame, max_rows: int = MAX_PREVIEW_ROWS) -> list[dict]:
    """Return first N rows as list of dicts for JSON preview."""
    return df.head(max_rows).fillna("").to_dict(orient="records")


def get_dtypes(df: pd.DataFrame) -> dict[str, str]:
    """Return column name → dtype mapping."""
    return {col: str(dtype) for col, dtype in df.dtypes.items()}

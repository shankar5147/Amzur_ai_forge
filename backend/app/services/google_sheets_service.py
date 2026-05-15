"""Service for loading Google Sheets into Pandas DataFrames."""

from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO
from pathlib import Path

import httpx
import pandas as pd

from app.core.config import settings
from app.services.dataframe_service import DataFrameServiceError, _safe_clean

logger = logging.getLogger(__name__)

# Regex patterns to extract the spreadsheet ID from various Google Sheets URL formats
_SHEET_ID_PATTERNS = [
    re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
]


def _extract_sheet_id(url: str) -> str:
    """Extract the Google Sheets spreadsheet ID from a URL."""
    # Strip fragment and whitespace
    url = url.split("#")[0].strip()
    for pattern in _SHEET_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    raise DataFrameServiceError(
        "Could not extract spreadsheet ID from the provided URL. "
        "Please use a URL like: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/..."
    )


def _extract_gid(url: str) -> str:
    """Extract gid (sheet tab) from URL, default to '0'."""
    match = re.search(r"[#&?]gid=(\d+)", url)
    return match.group(1) if match else "0"


async def load_google_sheet(sheet_url: str) -> tuple[pd.DataFrame, str]:
    """
    Load a Google Sheet into a Pandas DataFrame.

    Strategy:
    1. If a service-account credentials file is configured, use the Google
       Sheets API (works for private / org-shared sheets).
    2. Otherwise fall back to the public CSV-export endpoint (only works
       for sheets shared as "Anyone with the link can view").

    Returns (DataFrame, sheet_title).
    """
    sheet_id = _extract_sheet_id(sheet_url)
    gid = _extract_gid(sheet_url)

    # --- Strategy 1: Authenticated via service account ---
    creds_path = settings.google_sheets_credentials_file
    if creds_path and Path(creds_path).is_file():
        return await _load_via_service_account(sheet_url, sheet_id, gid, creds_path)

    # --- Strategy 2: Public CSV export (no credentials) ---
    return await _load_via_public_export(sheet_url, sheet_id, gid)


# ---------------------------------------------------------------------------
# Strategy 1 – Google Sheets API with service-account credentials
# ---------------------------------------------------------------------------

def _load_sheet_sync(sheet_url: str, sheet_id: str, gid: str, creds_path: str) -> tuple[pd.DataFrame, str]:
    """Synchronous helper – called inside ``asyncio.to_thread``."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise DataFrameServiceError(
            "The 'gspread' and 'google-auth' packages are required for "
            "authenticated Google Sheets access. Install them with: "
            "pip install gspread google-auth"
        ) from exc

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
    except Exception as exc:
        raise DataFrameServiceError(
            f"Failed to authenticate with Google Sheets API: {exc}"
        ) from exc

    try:
        spreadsheet = client.open_by_url(sheet_url)
        sheet_title = spreadsheet.title

        # Pick the correct worksheet by gid
        worksheet = None
        gid_int = int(gid)
        for ws in spreadsheet.worksheets():
            if ws.id == gid_int:
                worksheet = ws
                break
        if worksheet is None:
            worksheet = spreadsheet.sheet1

        records = worksheet.get_all_records()
    except gspread.exceptions.APIError as exc:
        msg = str(exc)
        if "403" in msg or "PERMISSION_DENIED" in msg:
            raise DataFrameServiceError(
                "Permission denied. Share the Google Sheet with the service-account email "
                "shown in your credentials JSON file."
            ) from exc
        raise DataFrameServiceError(f"Google Sheets API error: {exc}") from exc
    except gspread.exceptions.SpreadsheetNotFound as exc:
        raise DataFrameServiceError(
            "Google Sheet not found. Check the URL and share it with the "
            "service-account email in your credentials JSON file."
        ) from exc
    except Exception as exc:
        raise DataFrameServiceError(
            f"Failed to read Google Sheet: {exc}"
        ) from exc

    if not records:
        raise DataFrameServiceError("The Google Sheet contains no data.")

    df = pd.DataFrame(records)
    df = _safe_clean(df)
    return df, sheet_title


async def _load_via_service_account(
    sheet_url: str, sheet_id: str, gid: str, creds_path: str,
) -> tuple[pd.DataFrame, str]:
    """Run the synchronous gspread call in a thread so we don't block the event loop."""
    try:
        return await asyncio.to_thread(_load_sheet_sync, sheet_url, sheet_id, gid, creds_path)
    except DataFrameServiceError:
        raise
    except Exception as exc:
        raise DataFrameServiceError(f"Failed to load Google Sheet: {exc}") from exc


# ---------------------------------------------------------------------------
# Strategy 2 – Public CSV export (no auth required)
# ---------------------------------------------------------------------------

async def _load_via_public_export(
    sheet_url: str, sheet_id: str, gid: str,
) -> tuple[pd.DataFrame, str]:
    """Fetch a publicly-shared Google Sheet via its CSV export URL."""
    export_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AIForge/1.0)",
        "Accept": "text/csv, application/csv, */*",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(export_url, headers=headers)

            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                logger.warning(
                    "Google Sheet returned HTML (likely not public). URL: %s, status: %s",
                    sheet_url, resp.status_code,
                )
                raise DataFrameServiceError(
                    "The Google Sheet is not publicly accessible. Either:\n"
                    "1. Set sheet sharing to 'Anyone with the link can view', OR\n"
                    "2. Configure GOOGLE_SHEETS_CREDENTIALS_FILE in your .env with a "
                    "service-account JSON key and share the sheet with the service-account email."
                )

            resp.raise_for_status()

    except DataFrameServiceError:
        raise
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.error("Google Sheet HTTP error %s for URL: %s", status_code, sheet_url)
        if status_code == 404:
            raise DataFrameServiceError(
                "Google Sheet not found. Check the URL and ensure it is shared."
            ) from exc
        if status_code in (401, 403):
            raise DataFrameServiceError(
                "Access denied. The sheet is not publicly shared. Either:\n"
                "1. Set sharing to 'Anyone with the link can view', OR\n"
                "2. Configure GOOGLE_SHEETS_CREDENTIALS_FILE in .env."
            ) from exc
        raise DataFrameServiceError(
            f"Failed to fetch Google Sheet (HTTP {status_code})."
        ) from exc
    except httpx.RequestError as exc:
        raise DataFrameServiceError(
            f"Network error fetching Google Sheet: {exc}"
        ) from exc

    try:
        df = pd.read_csv(BytesIO(resp.content))
    except Exception as exc:
        raise DataFrameServiceError(f"Failed to parse sheet data: {exc}") from exc

    if df.empty:
        raise DataFrameServiceError("The Google Sheet contains no data.")

    df = _safe_clean(df)
    sheet_title = f"Google Sheet ({sheet_id[:8]}…)"
    return df, sheet_title

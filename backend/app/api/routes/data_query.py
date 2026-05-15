"""API routes for CSV / Excel / Google Sheets data querying."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import (
    DataFileUploadResponse,
    DataQueryRequest,
    DataQueryResponse,
    DataSessionInfo,
    DataSessionListResponse,
    GoogleSheetLoadRequest,
    GoogleSheetLoadResponse,
)
from app.services.dataframe_agent_service import DataFrameAgentError, DataFrameAgentService
from app.services.dataframe_service import (
    DataFrameServiceError,
    create_session,
    get_dtypes,
    get_preview,
    get_session_df,
    load_dataframe_from_bytes,
    session_store,
    validate_file,
)
from app.services.google_sheets_service import load_google_sheet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-query", tags=["data-query"])

# Singleton agent (shares the LLM client)
_agent = DataFrameAgentService()


@router.post("/upload", response_model=DataFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_data_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> DataFileUploadResponse:
    """Upload a CSV or Excel file and create a data query session."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided.")

    try:
        # Read and validate
        file_bytes = await file.read()
        validate_file(file.filename, len(file_bytes))

        # Parse into DataFrame
        df = load_dataframe_from_bytes(file_bytes, file.filename)

        # Create session
        session_id = create_session(df, file.filename)

        return DataFileUploadResponse(
            session_id=session_id,
            file_name=file.filename,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns),
            preview=get_preview(df),
            dtypes=get_dtypes(df),
        )
    except DataFrameServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process uploaded file.")


@router.post("/google-sheet", response_model=GoogleSheetLoadResponse, status_code=status.HTTP_201_CREATED)
async def load_google_sheet_endpoint(
    payload: GoogleSheetLoadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GoogleSheetLoadResponse:
    """Load a publicly-shared Google Sheet and create a data query session."""
    try:
        df, sheet_title = await load_google_sheet(payload.sheet_url)
        session_id = create_session(df, sheet_title)

        return GoogleSheetLoadResponse(
            session_id=session_id,
            sheet_title=sheet_title,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns),
            preview=get_preview(df),
            dtypes=get_dtypes(df),
        )
    except DataFrameServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Google Sheet load failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load Google Sheet.")


@router.post("/ask", response_model=DataQueryResponse)
async def ask_data_question(
    payload: DataQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DataQueryResponse:
    """Ask a natural-language question about a loaded dataset."""
    try:
        df = get_session_df(payload.session_id)
        result = await _agent.ask(df, payload.question)

        return DataQueryResponse(
            session_id=payload.session_id,
            question=payload.question,
            answer=result["answer"],
            code=result.get("code"),
        )
    except DataFrameServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DataFrameAgentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error("Data query failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Query analysis failed.")


@router.get("/sessions", response_model=DataSessionListResponse)
async def list_data_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> DataSessionListResponse:
    """List all active data query sessions."""
    sessions = session_store.list_sessions()
    return DataSessionListResponse(
        sessions=[DataSessionInfo(**s) for s in sessions]
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a data query session."""
    if session_store.get(session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    session_store.remove(session_id)

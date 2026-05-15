from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.db_models import DatabaseConnection, DatabaseQuery, User
from app.models.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionListResponse,
    DatabaseConnectionOut,
    DatabaseConnectionUpdate,
    DatabaseQueryOut,
    DatabaseQueryRequest,
    DatabaseQueryResponse,
    DirectQueryRequest,
)
from app.services.database_query_service import DatabaseQueryService, DatabaseQueryServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/database", tags=["database"])

# Service instance
db_query_service = DatabaseQueryService()


# --- Database Connection Endpoints ---


@router.post("/connections", response_model=DatabaseConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_database_connection(
    connection: DatabaseConnectionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseConnectionOut:
    """Create a new database connection for the user."""
    try:
        # Validate connection string and test connection
        connection_string = DatabaseQueryService.validate_connection_string(
            connection.db_type, connection.host, connection.port, connection.username, connection.password, connection.database_name
        )

        await DatabaseQueryService.test_connection(connection_string)

        # If connection is successful, retrieve schema information
        engine = create_async_engine(connection_string, echo=False)
        schema_info = await DatabaseQueryService.get_schema_info(engine, connection.db_type)
        await engine.dispose()

        # Create the database connection record
        db_connection = DatabaseConnection(
            user_id=current_user.id,
            name=connection.name,
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
            username=connection.username,
            password=connection.password,  # In production, this should be encrypted
            ssl_enabled=connection.ssl_enabled,
            schema_info=schema_info,
        )

        db.add(db_connection)
        await db.commit()
        await db.refresh(db_connection)

        logger.info(f"Created database connection: {db_connection.id} for user {current_user.id}")
        return DatabaseConnectionOut.model_validate(db_connection)

    except DatabaseQueryServiceError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create database connection")


@router.get("/connections", response_model=DatabaseConnectionListResponse)
async def list_database_connections(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseConnectionListResponse:
    """List all database connections for the current user."""
    try:
        result = await db.execute(
            sa.select(DatabaseConnection).where(DatabaseConnection.user_id == current_user.id).order_by(DatabaseConnection.created_at.desc())
        )
        connections = result.scalars().all()

        return DatabaseConnectionListResponse(connections=[DatabaseConnectionOut.model_validate(c) for c in connections])

    except Exception as e:
        logger.error(f"Failed to list database connections: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list database connections")


@router.get("/connections/{connection_id}", response_model=DatabaseConnectionOut)
async def get_database_connection(
    connection_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseConnectionOut:
    """Get a specific database connection."""
    try:
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        return DatabaseConnectionOut.model_validate(connection)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get database connection: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get database connection")


@router.put("/connections/{connection_id}", response_model=DatabaseConnectionOut)
async def update_database_connection(
    connection_id: uuid.UUID,
    update_data: DatabaseConnectionUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseConnectionOut:
    """Update a database connection."""
    try:
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(connection, key, value)

        await db.commit()
        await db.refresh(connection)

        logger.info(f"Updated database connection: {connection.id}")
        return DatabaseConnectionOut.model_validate(connection)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update database connection: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update database connection")


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database_connection(
    connection_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a database connection."""
    try:
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        await db.delete(connection)
        await db.commit()

        logger.info(f"Deleted database connection: {connection.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete database connection: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete database connection")


# --- Database Query Endpoints ---


@router.post("/query", response_model=DatabaseQueryResponse)
async def execute_natural_language_query(
    query_request: DatabaseQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseQueryResponse:
    """
    Execute a natural language query against a connected database.

    Steps:
    1. Validate the connection belongs to the user
    2. Convert natural language to SQL using LLM
    3. Execute the SQL query
    4. Store the query and result in the database
    5. Return the results
    """
    try:
        # Get the database connection
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == query_request.connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        if not connection.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database connection is not active")

        # Generate SQL from natural language
        logger.info(f"Generating SQL for query: {query_request.natural_language_query}")
        sql_query = await db_query_service.generate_sql_from_natural_language(
            query_request.natural_language_query, connection.schema_info, connection.db_type
        )

        # Build connection string and create engine
        connection_string = DatabaseQueryService.validate_connection_string(
            connection.db_type,
            connection.host,
            connection.port,
            connection.username,
            connection.password,
            connection.database_name,
        )

        # Validate SQL before execution
        DatabaseQueryService.validate_sql(sql_query)

        engine = create_async_engine(connection_string, echo=False)

        # Execute the query
        logger.info(f"Executing SQL query: {sql_query}")
        query_results, execution_time_ms = await db_query_service.execute_query(engine, sql_query)
        await engine.dispose()

        # Store the query and result
        db_query = DatabaseQuery(
            connection_id=connection.id,
            natural_language_query=query_request.natural_language_query,
            generated_sql=sql_query,
            result=json.dumps(query_results, default=str),
            execution_time_ms=int(execution_time_ms),
        )

        db.add(db_query)
        await db.commit()
        await db.refresh(db_query)

        logger.info(f"Query executed successfully. Query ID: {db_query.id}")

        return DatabaseQueryResponse(
            query_id=db_query.id,
            generated_sql=sql_query,
            result=query_results,
            execution_time_ms=int(execution_time_ms),
        )

    except DatabaseQueryServiceError as e:
        logger.error(f"Query generation/execution error: {e}")
        # Store the error
        try:
            db_query = DatabaseQuery(
                connection_id=query_request.connection_id,
                natural_language_query=query_request.natural_language_query,
                generated_sql="",
                error=str(e),
            )
            db.add(db_query)
            await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to store error query: {db_error}")
            await db.rollback()

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during query execution: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute query")


@router.get("/queries/{connection_id}", response_model=list[DatabaseQueryOut])
async def get_connection_query_history(
    connection_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[DatabaseQueryOut]:
    """Get query history for a specific database connection."""
    try:
        # Verify connection belongs to user
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        # Get query history
        result = await db.execute(
            sa.select(DatabaseQuery)
            .where(DatabaseQuery.connection_id == connection_id)
            .order_by(DatabaseQuery.created_at.desc())
            .limit(limit)
        )
        queries = result.scalars().all()

        return [DatabaseQueryOut.model_validate(q) for q in queries]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get query history")


@router.get("/queries/detail/{query_id}", response_model=DatabaseQueryOut)
async def get_query_detail(
    query_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseQueryOut:
    """Get details of a specific query."""
    try:
        result = await db.execute(
            sa.select(DatabaseQuery)
            .where(DatabaseQuery.id == query_id)
            .join(DatabaseConnection)
            .where(DatabaseConnection.user_id == current_user.id)
        )
        query = result.scalar_one_or_none()

        if not query:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query not found")

        return DatabaseQueryOut.model_validate(query)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get query detail: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get query detail")


@router.post("/connections/{connection_id}/test")
async def test_connection(
    connection_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Test a database connection."""
    try:
        result = await db.execute(
            sa.select(DatabaseConnection).where(
                (DatabaseConnection.id == connection_id) & (DatabaseConnection.user_id == current_user.id)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        connection_string = DatabaseQueryService.validate_connection_string(
            connection.db_type,
            connection.host,
            connection.port,
            connection.username,
            connection.password,
            connection.database_name,
        )

        await DatabaseQueryService.test_connection(connection_string)

        return {"status": "success", "message": "Connection test passed"}

    except DatabaseQueryServiceError as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connection test failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during connection test: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connection test failed")


# --- Direct Query (uses DATABASE_URL from .env) ---

# Cache schema info so we don't re-fetch on every query
_cached_schema_info: str | None = None


@router.post("/direct-query", response_model=DatabaseQueryResponse)
async def direct_query(
    query_request: DirectQueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DatabaseQueryResponse:
    """
    Execute a natural language query directly against the application database
    configured via DATABASE_URL in .env. No connection setup required.
    """
    global _cached_schema_info

    try:
        connection_string = settings.database_url
        if not connection_string:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="DATABASE_URL is not configured.",
            )

        engine = create_async_engine(connection_string, echo=False)

        # Determine db_type from the connection string
        if "postgresql" in connection_string:
            db_type = "postgresql"
        elif "mysql" in connection_string:
            db_type = "mysql"
        elif "sqlite" in connection_string:
            db_type = "sqlite"
        else:
            db_type = "postgresql"

        # Fetch and cache schema info
        if _cached_schema_info is None:
            _cached_schema_info = await DatabaseQueryService.get_schema_info(engine, db_type)

        # Generate SQL from natural language
        logger.info(f"Direct query from user {current_user.id}: {query_request.natural_language_query}")
        sql_query = await db_query_service.generate_sql_from_natural_language(
            query_request.natural_language_query, _cached_schema_info, db_type
        )

        # Validate SQL
        DatabaseQueryService.validate_sql(sql_query)

        # Execute the query
        query_results, execution_time_ms = await db_query_service.execute_query(engine, sql_query)
        await engine.dispose()

        return DatabaseQueryResponse(
            generated_sql=sql_query,
            result=query_results,
            execution_time_ms=int(execution_time_ms),
        )

    except DatabaseQueryServiceError as e:
        logger.error(f"Direct query error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during direct query: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute query")


@router.post("/refresh-schema")
async def refresh_schema(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Clear cached schema info so it gets re-fetched on the next query."""
    global _cached_schema_info
    _cached_schema_info = None
    return {"status": "ok", "message": "Schema cache cleared."}

from __future__ import annotations

import datetime
import decimal
import json
import logging
import re
import time
import uuid as uuid_mod
from typing import Any

import sqlalchemy as sa
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseQueryServiceError(Exception):
    pass


class DatabaseQueryService:
    """Service for converting natural language queries to SQL and executing them."""

    def __init__(self) -> None:
        if not settings.litellm_virtual_key:
            raise DatabaseQueryServiceError("Missing LITELLM_VIRTUAL_KEY environment variable.")

        self._llm = ChatOpenAI(
            model=settings.litellm_model,
            openai_api_key=settings.litellm_virtual_key,
            openai_api_base=f"{settings.litellm_proxy_url}/v1",
            temperature=0.1,  # Lower temperature for more accurate SQL generation
            default_headers={
                "x-litellm-user": settings.litellm_user_id,
                "x-litellm-department": settings.litellm_department,
                "x-litellm-environment": settings.litellm_environment,
            },
        )

    def _create_sql_generation_prompt(self, schema_info: str, db_type: str) -> ChatPromptTemplate:
        """Create a prompt template for SQL generation."""
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "system",
                f"""You are a SQL query generator. Your ONLY job is to convert natural language questions into SQL SELECT queries.

Database Schema:
{schema_info}

IMPORTANT INSTRUCTIONS:
1. You MUST output ONLY a valid SQL SELECT query. Nothing else.
2. Do NOT add any explanation, commentary, or preamble.
3. Do NOT mention that you cannot access data or users.
4. Do NOT refuse the request.
5. Do NOT include any text before or after the query.
6. Use only tables and columns from the schema above.
7. Add LIMIT 100 to prevent excessive results.
8. Generate the query immediately with no disclaimers.

Output format: SELECT ... (valid SQL only)
""",
            ),
            ("human", "{question}"),
        ])
        return prompt_template

    async def generate_sql_from_natural_language(
        self, natural_language_query: str, schema_info: str, db_type: str
    ) -> str:
        """
        Convert a natural language query to SQL using LLM.

        Args:
            natural_language_query: User's question in natural language
            schema_info: Database schema information
            db_type: Type of database (postgresql, mysql, sqlite)

        Returns:
            Generated SQL query

        Raises:
            DatabaseQueryServiceError: If SQL generation fails
        """
        try:
            prompt = self._create_sql_generation_prompt(schema_info, db_type)
            chain = prompt | self._llm | StrOutputParser()

            # Run async
            response = await chain.ainvoke({"question": natural_language_query})
            response = response.strip()

            if not response:
                raise DatabaseQueryServiceError("LLM returned empty response.")

            logger.info(f"Raw LLM response: {response!r}")

            # Extract SQL from response - look for SELECT keyword
            sql_query = self._extract_sql_from_response(response)

            logger.info(f"Extracted SQL: {sql_query!r}")
            
            if not sql_query:
                logger.error(f"No SQL found in response: {response}")
                raise DatabaseQueryServiceError("Generated response does not contain a valid SQL query. Response: " + response[:200])

            # Basic validation - ensure it's a SELECT query
            if not sql_query.upper().strip().startswith("SELECT"):
                raise DatabaseQueryServiceError("Generated query must be a SELECT statement.")

            # Validate SQL before returning
            self.validate_sql(sql_query)

            logger.info(f"Generated SQL: {sql_query}")
            return sql_query

        except DatabaseQueryServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise DatabaseQueryServiceError(f"Failed to generate SQL: {str(e)}")

    @staticmethod
    def validate_sql(sql_query: str) -> None:
        """
        Validate that a SQL query is safe to execute.
        Blocks INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, and other destructive statements.

        Raises:
            DatabaseQueryServiceError: If the query contains blocked keywords.
        """
        blocked_keywords = [
            r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b",
            r"\bDROP\b", r"\bALTER\b", r"\bTRUNCATE\b",
            r"\bCREATE\b", r"\bGRANT\b", r"\bREVOKE\b",
            r"\bEXEC\b", r"\bEXECUTE\b",
        ]
        upper_sql = sql_query.upper()
        for pattern in blocked_keywords:
            if re.search(pattern, upper_sql):
                keyword = pattern.replace(r"\b", "").strip()
                raise DatabaseQueryServiceError(
                    f"Blocked: {keyword} statements are not allowed. Only SELECT queries are permitted."
                )

    async def execute_query(
        self, engine: AsyncEngine, sql_query: str, max_rows: int = 1000
    ) -> tuple[list[dict[str, Any]], float]:
        """
        Execute a SQL query against the database.

        Args:
            engine: SQLAlchemy engine instance
            sql_query: SQL query to execute
            max_rows: Maximum number of rows to return

        Returns:
            Tuple of (results as list of dicts, execution time in ms)

        Raises:
            DatabaseQueryServiceError: If query execution fails
        """
        try:
            start_time = time.time()

            # Add LIMIT if not present
            if "LIMIT" not in sql_query.upper():
                sql_query = f"{sql_query.rstrip(';')} LIMIT {max_rows}"
            else:
                sql_query = sql_query.rstrip(";")

            async def _execute() -> list[dict[str, Any]]:
                async with engine.connect() as conn:
                    result = await conn.execute(text(sql_query))
                    columns = list(result.keys())
                    rows = result.fetchall()

                    # Convert rows to list of dicts with JSON-safe values
                    results = [
                        {col: self._make_serializable(val) for col, val in zip(columns, row)}
                        for row in rows
                    ]
                    return results

            results = await _execute()
            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(f"Query executed successfully. Returned {len(results)} rows in {execution_time_ms:.2f}ms")
            return results, execution_time_ms

        except SQLAlchemyError as e:
            logger.error(f"Database error: {e}")
            raise DatabaseQueryServiceError(f"Database error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            raise DatabaseQueryServiceError(f"Query execution failed: {str(e)}")

    @staticmethod
    def _make_serializable(value: Any) -> Any:
        """Convert non-JSON-serializable database values to safe types."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, decimal.Decimal):
            return float(value)
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        if isinstance(value, datetime.timedelta):
            return str(value)
        if isinstance(value, uuid_mod.UUID):
            return str(value)
        if isinstance(value, bytes):
            return value.hex()
        if isinstance(value, (list, tuple)):
            return [DatabaseQueryService._make_serializable(v) for v in value]
        if isinstance(value, dict):
            return {k: DatabaseQueryService._make_serializable(v) for k, v in value.items()}
        # Fallback
        return str(value)

    @staticmethod
    def _extract_sql_from_response(response: str) -> str:
        """
        Extract SQL query from LLM response.
        Handles cases where LLM returns explanatory text along with SQL,
        or wraps SQL in markdown code blocks.
        """
        response = response.strip()

        # Strip markdown code fences (```sql ... ``` or ``` ... ```)
        if "```" in response:
            import re
            match = re.search(r"```(?:sql)?\s*\n?(.*?)```", response, re.DOTALL | re.IGNORECASE)
            if match:
                response = match.group(1).strip()

        # Look for SELECT keyword
        select_index = response.upper().find("SELECT")
        if select_index == -1:
            return ""
        
        # Extract from SELECT onwards
        sql = response[select_index:].strip()
        
        # Remove trailing explanatory text (if any)
        patterns = ["\n\nNote:", "\n\nThis query:", "\n\nThe query:", "\nI cannot", "\nNote that"]
        for pattern in patterns:
            idx = sql.upper().find(pattern.upper())
            if idx > 0:
                sql = sql[:idx].strip()

        # Clean up: remove any remaining backticks and trailing semicolons
        sql = sql.strip("`").strip().rstrip(";").strip()
        
        return sql

    @staticmethod
    def validate_connection_string(db_type: str, host: str, port: int, username: str, password: str, database_name: str) -> str:
        """
        Build and validate a database connection string.

        Args:
            db_type: Type of database
            host: Database host
            port: Database port
            username: Database username
            password: Database password
            database_name: Database name

        Returns:
            Valid connection string

        Raises:
            DatabaseQueryServiceError: If connection string is invalid
        """
        try:
            db_type = db_type.lower()

            driver_map = {
                "postgresql": "postgresql+asyncpg",
                "mysql": "mysql+aiomysql",
                "sqlite": "sqlite+aiosqlite",
            }

            if db_type not in driver_map:
                raise DatabaseQueryServiceError(f"Unsupported database type: {db_type}")

            if db_type == "sqlite":
                url = sa.engine.URL.create(
                    drivername=driver_map[db_type],
                    database=database_name,
                )
            else:
                url = sa.engine.URL.create(
                    drivername=driver_map[db_type],
                    username=username,
                    password=password,
                    host=host,
                    port=port,
                    database=database_name,
                )

            return url.render_as_string(hide_password=False)

        except DatabaseQueryServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to build connection string: {e}")
            raise DatabaseQueryServiceError(f"Invalid database configuration: {str(e)}")

    @staticmethod
    async def test_connection(connection_string: str) -> bool:
        """
        Test if a database connection string is valid.

        Args:
            connection_string: Database connection string

        Returns:
            True if connection is successful

        Raises:
            DatabaseQueryServiceError: If connection fails
        """
        try:
            engine = create_async_engine(connection_string, echo=False, pool_pre_ping=True)

            async def _test() -> None:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            await _test()
            await engine.dispose()
            return True

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise DatabaseQueryServiceError(f"Failed to connect to database: {str(e)}")

    @staticmethod
    async def get_schema_info(engine: AsyncEngine, db_type: str) -> str:
        """
        Extract schema information from the database.

        Args:
            engine: SQLAlchemy engine instance
            db_type: Type of database

        Returns:
            Formatted schema information

        Raises:
            DatabaseQueryServiceError: If schema extraction fails
        """
        try:
            db_type = db_type.lower()

            async def _get_schema() -> str:
                async with engine.connect() as conn:
                    if db_type == "postgresql":
                        # PostgreSQL: Get tables and columns
                        query = """
                            SELECT 
                                table_name,
                                column_name,
                                data_type,
                                is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                            ORDER BY table_name, ordinal_position
                        """
                    elif db_type == "mysql":
                        # MySQL: Get tables and columns
                        query = """
                            SELECT 
                                TABLE_NAME as table_name,
                                COLUMN_NAME as column_name,
                                COLUMN_TYPE as data_type,
                                IS_NULLABLE as is_nullable
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                            ORDER BY TABLE_NAME, ORDINAL_POSITION
                        """
                    elif db_type == "sqlite":
                        # SQLite: Use pragma
                        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                        tables = [row[0] for row in result.fetchall()]
                        schema_parts = []

                        for table_name in tables:
                            result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
                            columns = result.fetchall()
                            schema_parts.append(f"\nTable: {table_name}")
                            for col in columns:
                                schema_parts.append(f"  - {col[1]}: {col[2]}")

                        return "\n".join(schema_parts)
                    else:
                        raise DatabaseQueryServiceError(f"Unsupported database type: {db_type}")

                    result = await conn.execute(text(query))
                    rows = result.fetchall()

                    # Format schema information
                    schema_parts = []
                    current_table = None

                    for row in rows:
                        table_name = row[0]
                        if table_name != current_table:
                            current_table = table_name
                            schema_parts.append(f"\nTable: {table_name}")

                        column_name = row[1]
                        data_type = row[2]
                        is_nullable = row[3]
                        nullable_str = "NULL" if is_nullable == "YES" else "NOT NULL"
                        schema_parts.append(f"  - {column_name}: {data_type} ({nullable_str})")

                    return "\n".join(schema_parts)

            schema_info = await _get_schema()

            if not schema_info.strip():
                raise DatabaseQueryServiceError("No tables found in the database.")

            return schema_info

        except DatabaseQueryServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            raise DatabaseQueryServiceError(f"Failed to retrieve schema: {str(e)}")

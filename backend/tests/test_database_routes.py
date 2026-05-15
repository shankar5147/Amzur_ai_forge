import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import DatabaseConnection, DatabaseQuery


class TestDatabaseConnections:
    """Tests for database connection endpoints."""

    @pytest.mark.asyncio
    async def test_create_database_connection(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test creating a new database connection."""
        payload = {
            "name": "Test PostgreSQL",
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "test_db",
            "username": "testuser",
            "password": "testpass",
            "ssl_enabled": False,
        }

        with patch("app.api.routes.database.DatabaseQueryService.test_connection", new_callable=AsyncMock) as mock_test:
            with patch("app.api.routes.database.DatabaseQueryService.get_schema_info", new_callable=AsyncMock) as mock_schema:
                mock_test.return_value = True
                mock_schema.return_value = "Table: users\n  - id: INTEGER\n  - name: VARCHAR"

                response = await client.post(
                    "/api/database/connections",
                    json=payload,
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test PostgreSQL"
        assert data["db_type"] == "postgresql"
        assert data["host"] == "localhost"
        assert data["port"] == 5432
        assert data["database_name"] == "test_db"
        assert data["schema_info"] == "Table: users\n  - id: INTEGER\n  - name: VARCHAR"

    @pytest.mark.asyncio
    async def test_create_database_connection_invalid_type(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Test creating database connection with invalid db_type."""
        payload = {
            "name": "Test",
            "db_type": "invalid",
            "host": "localhost",
            "port": 5432,
            "database_name": "test_db",
            "username": "testuser",
            "password": "testpass",
            "ssl_enabled": False,
        }

        response = await client.post(
            "/api/database/connections",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_database_connection_test_fails(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Test creating database connection when connection test fails."""
        payload = {
            "name": "Test PostgreSQL",
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "test_db",
            "username": "testuser",
            "password": "wrongpass",
            "ssl_enabled": False,
        }

        with patch("app.api.routes.database.DatabaseQueryService.test_connection", new_callable=AsyncMock) as mock_test:
            mock_test.side_effect = Exception("Connection refused")

            response = await client.post(
                "/api/database/connections",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_list_database_connections(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test listing all database connections."""
        # Create test connections
        conn1 = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="user1",
            password="pass1",
            ssl_enabled=False,
            schema_info="Schema 1",
        )
        conn2 = DatabaseConnection(
            user_id=test_user.id,
            name="MySQL",
            db_type="mysql",
            host="localhost",
            port=3306,
            database_name="test_db2",
            username="user2",
            password="pass2",
            ssl_enabled=True,
            schema_info="Schema 2",
        )
        db_session.add(conn1)
        db_session.add(conn2)
        await db_session.commit()

        response = await client.get(
            "/api/database/connections",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["connections"]) == 2
        assert data["connections"][0]["name"] == "MySQL"  # Most recent first
        assert data["connections"][1]["name"] == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_get_database_connection(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test getting a specific database connection."""
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Schema info",
        )
        db_session.add(conn)
        await db_session.commit()

        response = await client.get(
            f"/api/database/connections/{conn.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(conn.id)
        assert data["name"] == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_get_database_connection_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Test getting non-existent database connection."""
        fake_id = uuid.uuid4()

        response = await client.get(
            f"/api/database/connections/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_database_connection(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test deleting a database connection."""
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Schema info",
        )
        db_session.add(conn)
        await db_session.commit()

        response = await client.delete(
            f"/api/database/connections/{conn.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        result = await db_session.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn.id))
        assert result.scalar_one_or_none() is None


class TestDatabaseQueries:
    """Tests for database query endpoints."""

    @pytest.mark.asyncio
    async def test_execute_natural_language_query(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test executing a natural language query."""
        # Create a test connection
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Table: users\n  - id: INTEGER\n  - name: VARCHAR",
            is_active=True,
        )
        db_session.add(conn)
        await db_session.commit()

        payload = {
            "connection_id": str(conn.id),
            "natural_language_query": "Show me all users",
        }

        mock_results = [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

        with patch("app.api.routes.database.db_query_service.generate_sql_from_natural_language", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.database.db_query_service.execute_query", new_callable=AsyncMock) as mock_exec:
                mock_gen.return_value = "SELECT * FROM users LIMIT 1000"
                mock_exec.return_value = (mock_results, 123.45)

                response = await client.post(
                    "/api/database/query",
                    json=payload,
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["generated_sql"] == "SELECT * FROM users LIMIT 1000"
        assert data["result"] == mock_results
        assert abs(data["execution_time_ms"] - 123) < 1  # Allow small rounding difference

    @pytest.mark.asyncio
    async def test_execute_query_connection_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Test executing query with non-existent connection."""
        payload = {
            "connection_id": str(uuid.uuid4()),
            "natural_language_query": "Show me all users",
        }

        response = await client.post(
            "/api/database/query",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_execute_query_connection_inactive(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test executing query with inactive connection."""
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Schema info",
            is_active=False,
        )
        db_session.add(conn)
        await db_session.commit()

        payload = {
            "connection_id": str(conn.id),
            "natural_language_query": "Show me all users",
        }

        response = await client.post(
            "/api/database/query",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_query_history(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test getting query history for a connection."""
        # Create a test connection
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Schema info",
        )
        db_session.add(conn)
        await db_session.commit()

        # Create test queries
        q1 = DatabaseQuery(
            connection_id=conn.id,
            natural_language_query="Show users",
            generated_sql="SELECT * FROM users",
            result=json.dumps([{"id": 1, "name": "John"}]),
            execution_time_ms=100,
        )
        q2 = DatabaseQuery(
            connection_id=conn.id,
            natural_language_query="Show orders",
            generated_sql="SELECT * FROM orders",
            result=json.dumps([{"id": 1, "total": 100}]),
            execution_time_ms=150,
        )
        db_session.add(q1)
        db_session.add(q2)
        await db_session.commit()

        response = await client.get(
            f"/api/database/queries/{conn.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["natural_language_query"] == "Show orders"  # Most recent first

    @pytest.mark.asyncio
    async def test_test_connection(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user
    ) -> None:
        """Test connection test endpoint."""
        conn = DatabaseConnection(
            user_id=test_user.id,
            name="PostgreSQL",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="test_db",
            username="testuser",
            password="testpass",
            ssl_enabled=False,
            schema_info="Schema info",
        )
        db_session.add(conn)
        await db_session.commit()

        with patch("app.api.routes.database.DatabaseQueryService.test_connection", new_callable=AsyncMock) as mock_test:
            mock_test.return_value = True

            response = await client.post(
                f"/api/database/connections/{conn.id}/test",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"

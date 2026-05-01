"""Tests for thread API routes."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.db_models import User
from app.services.thread_service import ThreadService


class TestCreateThreadEndpoint:
    @pytest.mark.asyncio
    async def test_create_thread_default_name(self, client: AsyncClient, auth_headers: dict, db_session):
        resp = await client.post("/api/threads", json={}, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Chat"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_thread_custom_name(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/threads", json={"name": "My Topic"}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Topic"

    @pytest.mark.asyncio
    async def test_create_thread_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/threads", json={})
        assert resp.status_code == 401


class TestListThreadsEndpoint:
    @pytest.mark.asyncio
    async def test_list_empty_threads(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/threads", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["threads"] == []

    @pytest.mark.asyncio
    async def test_list_threads_returns_created(self, client: AsyncClient, auth_headers: dict):
        await client.post("/api/threads", json={"name": "Thread 1"}, headers=auth_headers)
        await client.post("/api/threads", json={"name": "Thread 2"}, headers=auth_headers)
        resp = await client.get("/api/threads", headers=auth_headers)
        assert resp.status_code == 200
        threads = resp.json()["threads"]
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_list_threads_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/threads")
        assert resp.status_code == 401


class TestUpdateThreadEndpoint:
    @pytest.mark.asyncio
    async def test_update_thread_name(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post("/api/threads", json={"name": "Old"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        resp = await client.patch(f"/api/threads/{thread_id}", json={"name": "Renamed"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_update_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(f"/api/threads/{fake_id}", json={"name": "X"}, headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_thread_unauthenticated(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(f"/api/threads/{fake_id}", json={"name": "X"})
        assert resp.status_code == 401


class TestDeleteThreadEndpoint:
    @pytest.mark.asyncio
    async def test_delete_thread(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post("/api/threads", json={"name": "To Delete"}, headers=auth_headers)
        thread_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/threads/{thread_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify gone
        list_resp = await client.get("/api/threads", headers=auth_headers)
        assert len(list_resp.json()["threads"]) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/api/threads/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

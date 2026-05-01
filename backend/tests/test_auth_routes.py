"""Tests for auth API routes."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.db_models import User


class TestSignupEndpoint:
    @pytest.mark.asyncio
    async def test_signup_success(self, client: AsyncClient):
        resp = await client.post("/api/auth/signup", json={
            "email": "newuser@amzur.com",
            "password": "StrongPass1!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "newuser@amzur.com"
        assert data["user"]["full_name"] == "New User"
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_signup_duplicate_email(self, client: AsyncClient, test_user: User):
        resp = await client.post("/api/auth/signup", json={
            "email": test_user.email,
            "password": "StrongPass1!",
            "full_name": "Duplicate",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_signup_short_password(self, client: AsyncClient):
        resp = await client.post("/api/auth/signup", json={
            "email": "short@amzur.com",
            "password": "short",
            "full_name": "Short Pass",
        })
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_signup_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/auth/signup", json={
            "email": "not-an-email",
            "password": "ValidPass1!",
            "full_name": "Bad Email",
        })
        assert resp.status_code == 422


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        resp = await client.post("/api/auth/login", json={
            "email": "test@amzur.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@amzur.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        resp = await client.post("/api/auth/login", json={
            "email": "test@amzur.com",
            "password": "WrongPass!",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/auth/login", json={
            "email": "noone@amzur.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401


class TestGoogleAuthEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.routes.auth.id_token.verify_oauth2_token")
    async def test_google_auth_new_user(self, mock_verify, client: AsyncClient):
        mock_verify.return_value = {
            "sub": "google_id_123",
            "email": "googleuser@amzur.com",
            "name": "Google User",
            "picture": "https://lh3.google.com/photo.jpg",
        }
        resp = await client.post("/api/auth/google", json={
            "credential": "fake-google-token",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "googleuser@amzur.com"
        assert data["user"]["full_name"] == "Google User"
        assert "access_token" in data

    @pytest.mark.asyncio
    @patch("app.api.routes.auth.id_token.verify_oauth2_token")
    async def test_google_auth_existing_email_links(self, mock_verify, client: AsyncClient, test_user: User):
        mock_verify.return_value = {
            "sub": "google_id_456",
            "email": test_user.email,
            "name": "Test User",
            "picture": "https://lh3.google.com/photo2.jpg",
        }
        resp = await client.post("/api/auth/google", json={
            "credential": "fake-token",
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["id"] == str(test_user.id)

    @pytest.mark.asyncio
    @patch("app.api.routes.auth.id_token.verify_oauth2_token")
    async def test_google_auth_invalid_token(self, mock_verify, client: AsyncClient):
        mock_verify.side_effect = ValueError("Invalid token")
        resp = await client.post("/api/auth/google", json={
            "credential": "bad-token",
        })
        assert resp.status_code == 401
        assert "Invalid Google token" in resp.json()["detail"]

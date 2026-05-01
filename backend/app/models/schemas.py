from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Auth Schemas ---

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token from frontend


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


# --- Thread Schemas ---

class ThreadCreate(BaseModel):
    name: str = Field(default="New Chat", max_length=255)


class ThreadUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ThreadOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThreadListResponse(BaseModel):
    threads: list[ThreadOut]


# --- Chat Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    thread_id: uuid.UUID | None = None  # If None, create a new thread


class ChatResponse(BaseModel):
    response: str
    thread_id: uuid.UUID


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[MessageOut]


# Fix forward reference
AuthResponse.model_rebuild()

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


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
    message: str | None = Field(default=None, max_length=4000)
    thread_id: uuid.UUID | None = None  # If None, create a new thread
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> ChatRequest:
        if self.message:
            self.message = self.message.strip()
        if not self.message and not self.attachment_ids:
            raise ValueError("Either message text or at least one attachment is required.")
        return self


class ChatResponse(BaseModel):
    response: str
    thread_id: uuid.UUID


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    attachments: list[AttachmentOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[MessageOut]


class AttachmentOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    message_id: uuid.UUID | None
    file_name: str
    mime_type: str
    file_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadAttachmentsResponse(BaseModel):
    attachments: list[AttachmentOut]


class AttachmentPreviewResponse(BaseModel):
    attachment_id: uuid.UUID
    file_name: str
    mime_type: str
    preview_type: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    content: str | None = None
    truncated: bool = False


class GeneratedImageOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    thread_id: uuid.UUID
    prompt: str
    image_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=3)
    thread_id: uuid.UUID | None = None
    message: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_payload(self) -> ImageGenerationRequest:
        self.prompt = self.prompt.strip()
        if self.message:
            self.message = self.message.strip()
        if not self.prompt:
            raise ValueError("Prompt is required.")
        return self


class ImageGenerationResponse(BaseModel):
    thread_id: uuid.UUID
    user_message: MessageOut
    assistant_message: MessageOut
    image: GeneratedImageOut


# Fix forward reference
AuthResponse.model_rebuild()

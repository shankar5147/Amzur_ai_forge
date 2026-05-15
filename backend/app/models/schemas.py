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


# --- Database Connection Schemas ---

class DatabaseConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    db_type: str = Field(..., description="Database type: postgresql, mysql, sqlite")
    host: str = Field(..., max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., max_length=255)
    username: str = Field(..., max_length=255)
    password: str = Field(..., max_length=512)
    ssl_enabled: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_db_type(self) -> DatabaseConnectionCreate:
        if self.db_type.lower() not in ["postgresql", "mysql", "sqlite"]:
            raise ValueError("db_type must be one of: postgresql, mysql, sqlite")
        return self


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=512)
    is_active: bool | None = None


class DatabaseConnectionOut(BaseModel):
    id: uuid.UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool
    is_active: bool
    schema_info: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatabaseConnectionListResponse(BaseModel):
    connections: list[DatabaseConnectionOut]


class DatabaseQueryRequest(BaseModel):
    connection_id: uuid.UUID
    natural_language_query: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def validate_query(self) -> DatabaseQueryRequest:
        self.natural_language_query = self.natural_language_query.strip()
        if not self.natural_language_query:
            raise ValueError("Query text cannot be empty.")
        return self


class DatabaseQueryOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    natural_language_query: str
    generated_sql: str
    result: str | None = None
    error: str | None = None
    execution_time_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatabaseQueryResponse(BaseModel):
    query_id: uuid.UUID | None = None
    generated_sql: str
    result: dict | list | str | None = None
    error: str | None = None
    execution_time_ms: int | None = None


class DirectQueryRequest(BaseModel):
    natural_language_query: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def validate_query(self) -> DirectQueryRequest:
        self.natural_language_query = self.natural_language_query.strip()
        if not self.natural_language_query:
            raise ValueError("Query text cannot be empty.")
        return self


class ImageGenerationResponse(BaseModel):
    thread_id: uuid.UUID
    user_message: MessageOut
    assistant_message: MessageOut
    image: GeneratedImageOut


# --- Data Query (CSV / Excel / Google Sheets) Schemas ---

class DataFileUploadResponse(BaseModel):
    session_id: str
    file_name: str
    row_count: int
    column_count: int
    columns: list[str]
    preview: list[dict]
    dtypes: dict[str, str]


class GoogleSheetLoadRequest(BaseModel):
    sheet_url: str = Field(..., min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_url(self) -> GoogleSheetLoadRequest:
        self.sheet_url = self.sheet_url.strip()
        if "docs.google.com/spreadsheets" not in self.sheet_url:
            raise ValueError("Must be a valid Google Sheets URL.")
        return self


class GoogleSheetLoadResponse(BaseModel):
    session_id: str
    sheet_title: str
    row_count: int
    column_count: int
    columns: list[str]
    preview: list[dict]
    dtypes: dict[str, str]


class DataQueryRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def validate_question(self) -> DataQueryRequest:
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("Question cannot be empty.")
        return self


class DataQueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    code: str | None = None


class DataSessionInfo(BaseModel):
    session_id: str
    file_name: str
    row_count: int
    column_count: int
    columns: list[str]
    dtypes: dict[str, str]


class DataSessionListResponse(BaseModel):
    sessions: list[DataSessionInfo]


# Fix forward reference
AuthResponse.model_rebuild()

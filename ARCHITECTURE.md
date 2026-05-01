# AI Forge Chatbot — Architecture & Best Practices

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Technology Stack](#2-technology-stack)
- [3. Architecture Diagram](#3-architecture-diagram)
- [4. Backend Architecture](#4-backend-architecture)
- [5. Frontend Architecture](#5-frontend-architecture)
- [6. Authentication & Security](#6-authentication--security)
- [7. Database Design](#7-database-design)
- [8. API Contract](#8-api-contract)
- [9. Coding Standards](#9-coding-standards)
- [10. Best Practices Implemented](#10-best-practices-implemented)
- [11. Testing Strategy](#11-testing-strategy)
- [12. Development Workflow](#12-development-workflow)

---

## 1. Project Overview

AI Forge Chatbot is a full-stack conversational AI application that provides a ChatGPT-like interface for Amzur employees. It features multi-threaded conversations, dual authentication (email/password + Google OAuth), and LLM-powered responses via a LiteLLM proxy gateway.

**Key Features:**

- Real-time AI chat with markdown rendering
- Conversation threads (create, rename, delete)
- Dual authentication: email/password + Google OAuth
- Persistent chat history per thread
- Auto-generated thread names using AI
- Responsive UI with collapsible sidebar

---

## 2. Technology Stack

### Backend

| Layer        | Technology                   | Version          |
| ------------ | ---------------------------- | ---------------- |
| Framework    | FastAPI                      | ≥0.116.0         |
| Runtime      | Python                       | 3.14             |
| Server       | Uvicorn (ASGI)               | ≥0.35.0          |
| ORM          | SQLAlchemy 2.0 (async)       | ≥2.0.40          |
| Database     | PostgreSQL (Supabase)        | —                |
| DB Driver    | asyncpg                      | ≥0.31.0          |
| Auth         | PyJWT + bcrypt               | ≥2.10.0 / ≥4.3.0 |
| LLM          | LangChain + LangChain-OpenAI | ≥0.3.27          |
| Validation   | Pydantic v2                  | ≥2.13.0          |
| Google OAuth | google-auth                  | —                |

### Frontend

| Layer        | Technology                  | Version |
| ------------ | --------------------------- | ------- |
| Framework    | React                       | 19      |
| Language     | TypeScript                  | 5.9     |
| Build Tool   | Vite                        | 8.x     |
| Styling      | Tailwind CSS v4             | 4.2     |
| Routing      | react-router-dom            | 7.x     |
| Markdown     | react-markdown + remark-gfm | 10.x    |
| Google OAuth | @react-oauth/google         | 0.13.x  |
| Testing      | Vitest + Testing Library    | —       |

### Infrastructure

| Component   | Technology                     |
| ----------- | ------------------------------ |
| LLM Gateway | LiteLLM Proxy (self-hosted)    |
| Database    | Supabase PostgreSQL            |
| LLM Model   | Gemini 2.5 Flash (via LiteLLM) |

---

## 3. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + TypeScript)            │
│                                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │LoginPage │  │ThreadSidebar │  │ChatMessages │  │Composer  │ │
│  └────┬─────┘  └──────┬───────┘  └──────┬──────┘  └────┬─────┘ │
│       │                │                  │              │        │
│       └────────────────┴──────────────────┴──────────────┘        │
│                              │                                    │
│                    ┌─────────┴──────────┐                        │
│                    │  AuthContext (JWT)  │                        │
│                    │  chatApi Service    │                        │
│                    └─────────┬──────────┘                        │
└──────────────────────────────┼────────────────────────────────────┘
                               │ HTTP (fetch)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI + Python)                   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    API Layer (Routes)                         │  │
│  │  /api/auth/*    /api/chat/*    /api/threads/*    /health     │  │
│  └────────┬──────────────┬─────────────┬───────────────────────┘  │
│           │              │             │                           │
│  ┌────────┴──────────────┴─────────────┴───────────────────────┐  │
│  │                   Service Layer                              │  │
│  │  AuthService    ChatService    ThreadService  MessageService │  │
│  └────────┬──────────────┬─────────────┬───────────────────────┘  │
│           │              │             │                           │
│  ┌────────┴──────┐  ┌───┴───┐  ┌─────┴───────────────────────┐  │
│  │Security/JWT   │  │LiteLLM│  │  SQLAlchemy (Async ORM)      │  │
│  │Google OAuth   │  │ Proxy │  │  PostgreSQL (Supabase)       │  │
│  └───────────────┘  └───┬───┘  └─────────────────────────────┘  │
└──────────────────────────┼────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   LiteLLM Proxy Server  │
              │  (litellm.amzur.com)    │
              │                         │
              │   ┌─────────────────┐   │
              │   │ Gemini 2.5 Flash│   │
              │   └─────────────────┘   │
              └─────────────────────────┘
```

---

## 4. Backend Architecture

### Directory Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app factory, lifespan, CORS, routers
│   ├── core/
│   │   ├── config.py           # Settings (dataclass, env-driven)
│   │   ├── database.py         # Async engine + session factory
│   │   └── security.py         # get_current_user dependency (JWT Bearer)
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py         # /api/auth/signup, /login, /google
│   │       ├── chat.py         # /api/chat, /api/chat/history/{id}
│   │       └── threads.py      # /api/threads CRUD
│   ├── models/
│   │   ├── db_models.py        # SQLAlchemy ORM models
│   │   └── schemas.py          # Pydantic request/response schemas
│   ├── services/
│   │   ├── auth_service.py     # Auth logic (bcrypt, JWT, OAuth linking)
│   │   ├── chat_service.py     # LLM chain (LangChain + LiteLLM)
│   │   ├── thread_service.py   # Thread CRUD operations
│   │   └── message_service.py  # Message persistence
│   └── prompts/
│       └── chat_prompt.py      # LangChain prompt templates
├── tests/                      # Pytest test suite
├── requirements.txt
└── .env
```

### Layered Architecture

The backend follows a strict **3-layer architecture**:

| Layer            | Responsibility                                         | Components                                |
| ---------------- | ------------------------------------------------------ | ----------------------------------------- |
| **API (Routes)** | HTTP handling, request validation, response formatting | `api/routes/*.py`                         |
| **Service**      | Business logic, orchestration                          | `services/*.py`                           |
| **Data**         | Database access, ORM models                            | `models/db_models.py`, `core/database.py` |

**Data flow:** Route → Service → Database (SQLAlchemy) / External API (LiteLLM)

### Key Design Decisions

1. **Async-first**: All database operations and HTTP handlers use `async/await` for non-blocking I/O
2. **Dependency Injection**: FastAPI's `Depends()` for DB sessions and authentication
3. **Service pattern**: Business logic isolated in service classes, testable independently
4. **Stateless JWT**: No server-side session storage; auth state carried in tokens

---

## 5. Frontend Architecture

### Directory Structure

```
front-end/
├── src/
│   ├── main.tsx                # Entry point (BrowserRouter + AuthProvider)
│   ├── App.tsx                 # ChatPage, routing, ProtectedRoute/PublicRoute
│   ├── components/
│   │   ├── LoginPage.tsx       # Login/Signup + Google OAuth UI
│   │   ├── ChatMessageList.tsx # Message display with Markdown
│   │   ├── ChatComposer.tsx    # Message input form
│   │   └── ThreadSidebar.tsx   # Thread list with rename/delete
│   ├── context/
│   │   └── AuthContext.tsx     # Global auth state (React Context)
│   ├── services/
│   │   └── chatApi.ts          # Centralized API client (fetch-based)
│   ├── types/
│   │   └── chat.ts             # TypeScript interfaces
│   └── test/                   # Vitest test suite
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .env
```

### Component Architecture

```
<BrowserRouter>
  <AuthProvider>
    <App>
      <Routes>
        ├── /login  → <PublicRoute><LoginPage /></PublicRoute>
        ├── /chat   → <ProtectedRoute><ChatPage /></ProtectedRoute>
        └── *       → Navigate to /chat
      </Routes>
    </App>
  </AuthProvider>
</BrowserRouter>
```

**ChatPage Composition:**

```
<ChatPage>
  ├── <ThreadSidebar />       (left panel)
  └── <main>
        ├── <header />        (app bar with user info + logout)
        ├── <ChatMessageList /> (scrollable message area)
        └── <ChatComposer />   (input form)
      </main>
</ChatPage>
```

### State Management

- **AuthContext** — Global auth state (token, user, loading) backed by `localStorage`
- **Component state** — Local `useState` for UI state (threads, messages, input, loading)
- **No external state library** — React Context + local state is sufficient for this app's complexity

---

## 6. Authentication & Security

### Authentication Flow

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│   Frontend  │     │   Backend     │     │  Google/DB   │
└──────┬──────┘     └───────┬───────┘     └──────┬───────┘
       │                    │                     │
       │ POST /api/auth/login (or /signup /google)│
       │───────────────────►│                     │
       │                    │  Verify credentials │
       │                    │────────────────────►│
       │                    │◄────────────────────│
       │                    │                     │
       │  { access_token, user }                  │
       │◄───────────────────│                     │
       │                    │                     │
       │ Store in localStorage                    │
       │                    │                     │
       │ GET /api/threads (Authorization: Bearer token)
       │───────────────────►│                     │
       │                    │ Decode JWT          │
       │                    │ Load User from DB   │
       │                    │────────────────────►│
       │                    │◄────────────────────│
       │   200 { threads }  │                     │
       │◄───────────────────│                     │
```

### Security Measures

| Measure                  | Implementation                                               |
| ------------------------ | ------------------------------------------------------------ |
| Password hashing         | bcrypt with auto-generated salt                              |
| JWT tokens               | HS256, 24-hour expiry, issued-at claim                       |
| Google OAuth             | Server-side token verification with `google-auth` library    |
| Clock skew tolerance     | 10-second allowance for Google token validation              |
| Route protection         | `get_current_user` dependency on all authenticated endpoints |
| CORS                     | Explicit origin allowlist + regex pattern                    |
| Input validation         | Pydantic schemas with min/max length constraints             |
| SQL injection prevention | SQLAlchemy ORM (parameterized queries)                       |
| Email validation         | Pydantic `EmailStr` type                                     |

---

## 7. Database Design

### Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────────┐
│       USERS          │       │        THREADS           │
├─────────────────────┤       ├─────────────────────────┤
│ id (UUID, PK)       │──┐    │ id (UUID, PK)           │
│ email (unique)      │  │    │ user_id (FK → users.id) │
│ hashed_password?    │  │    │ name                     │
│ full_name           │  ├───►│ created_at               │
│ google_id? (unique) │  │    │ updated_at               │
│ avatar_url?         │  │    └──────────┬──────────────┘
│ created_at          │  │               │
└─────────────────────┘  │               │ 1:N (cascade delete)
                          │               ▼
                          │    ┌─────────────────────────┐
                          │    │       MESSAGES           │
                          │    ├─────────────────────────┤
                          │    │ id (UUID, PK)           │
                          │    │ thread_id (FK → threads)│
                          └───►│ user_id (FK → users)    │
                               │ role ("user"|"assistant")│
                               │ content (Text)          │
                               │ created_at              │
                               └─────────────────────────┘
```

### Key Design Decisions

- **UUID primary keys** — Avoids sequential ID guessing; distributed-safe
- **Nullable `hashed_password`** — Supports Google-only users (no password)
- **Cascade deletes** — Deleting a thread removes all its messages
- **Timezone-aware timestamps** — All `DateTime` columns store UTC
- **Indexed foreign keys** — `user_id` and `thread_id` columns indexed for query performance

---

## 8. API Contract

### Authentication Endpoints

| Method | Endpoint           | Auth | Description                       |
| ------ | ------------------ | ---- | --------------------------------- |
| POST   | `/api/auth/signup` | No   | Create account (email + password) |
| POST   | `/api/auth/login`  | No   | Login with credentials            |
| POST   | `/api/auth/google` | No   | Login/register via Google OAuth   |

### Chat Endpoints

| Method | Endpoint                        | Auth | Description                                          |
| ------ | ------------------------------- | ---- | ---------------------------------------------------- |
| POST   | `/api/chat`                     | Yes  | Send message (creates thread if `thread_id` is null) |
| GET    | `/api/chat/history/{thread_id}` | Yes  | Get all messages in a thread                         |

### Thread Endpoints

| Method | Endpoint            | Auth | Description                        |
| ------ | ------------------- | ---- | ---------------------------------- |
| POST   | `/api/threads`      | Yes  | Create a new thread                |
| GET    | `/api/threads`      | Yes  | List user's threads (newest first) |
| PATCH  | `/api/threads/{id}` | Yes  | Rename a thread                    |
| DELETE | `/api/threads/{id}` | Yes  | Delete a thread and its messages   |

### Utility

| Method | Endpoint  | Auth | Description  |
| ------ | --------- | ---- | ------------ |
| GET    | `/health` | No   | Health check |

---

## 9. Coding Standards

### Backend (Python)

| Standard                                 | Implementation                                              |
| ---------------------------------------- | ----------------------------------------------------------- |
| **Type Hints**                           | All functions use `-> ReturnType` and parameter annotations |
| **`from __future__ import annotations`** | Enables PEP 604 unions (`str \| None`) in all modules       |
| **Frozen dataclass for config**          | Immutable settings, single source of truth                  |
| **Pydantic v2 `model_validate`**         | ORM-to-schema conversion with `from_attributes=True`        |
| **Async generators for DB sessions**     | `yield` pattern with context manager cleanup                |
| **Exception hierarchy**                  | `AuthError`, `LLMServiceError` — domain-specific errors     |
| **Route status codes**                   | Explicit `status_code=` on create endpoints (201, 204)      |
| **Service classes with DI**              | Accept `AsyncSession` via constructor, not global state     |

### Frontend (TypeScript)

| Standard                     | Implementation                                           |
| ---------------------------- | -------------------------------------------------------- |
| **Strict TypeScript**        | No `any` types; all API responses typed                  |
| **Interface-first design**   | Types defined in `types/chat.ts`, shared across codebase |
| **Named exports**            | All components use `export function ComponentName()`     |
| **Functional components**    | React hooks only — no class components                   |
| **Custom hooks**             | `useAuth()` for auth state access                        |
| **Centralized API client**   | Single `chatApi.ts` module with typed functions          |
| **Error boundaries**         | try/catch in async handlers with user feedback           |
| **Tailwind utility classes** | No custom CSS files per component                        |

### Naming Conventions

| Context               | Convention                                    | Example                                 |
| --------------------- | --------------------------------------------- | --------------------------------------- |
| Python files          | snake_case                                    | `auth_service.py`                       |
| Python classes        | PascalCase                                    | `AuthService`, `ThreadOut`              |
| Python functions      | snake_case                                    | `get_current_user`                      |
| TypeScript files      | PascalCase (components), camelCase (services) | `LoginPage.tsx`, `chatApi.ts`           |
| TypeScript interfaces | PascalCase                                    | `ChatMessage`, `AuthResponse`           |
| TypeScript functions  | camelCase                                     | `sendMessage`, `getThreads`             |
| API routes            | kebab-case                                    | `/api/auth/google`, `/api/chat/history` |
| Database tables       | snake_case plural                             | `users`, `threads`, `messages`          |

---

## 10. Best Practices Implemented

### Architecture & Design

| Practice                      | Details                                                                     |
| ----------------------------- | --------------------------------------------------------------------------- |
| **Separation of Concerns**    | API routes handle HTTP only; business logic in services; data access in ORM |
| **Dependency Injection**      | FastAPI `Depends()` for DB sessions and auth — enables testing              |
| **Single Responsibility**     | Each service handles one domain (auth, chat, threads, messages)             |
| **Interface Segregation**     | Pydantic schemas separate request/response shapes from DB models            |
| **Environment-driven config** | All secrets/settings in `.env`, loaded via `python-dotenv`                  |

### Security

| Practice                                  | Details                                               |
| ----------------------------------------- | ----------------------------------------------------- |
| **Password hashing with bcrypt**          | Industry-standard adaptive hash function              |
| **JWT with expiration**                   | 24-hour token validity, prevents stale sessions       |
| **Google OAuth server-side verification** | Token validated on backend, not trusted from frontend |
| **CORS origin allowlist**                 | Only specific origins can call the API                |
| **Input validation at boundary**          | Pydantic enforces min/max lengths, email format       |
| **No secrets in code**                    | All credentials in `.env` (gitignored)                |
| **Parameterized queries**                 | SQLAlchemy prevents SQL injection by design           |
| **UUID identifiers**                      | Non-enumerable, prevents IDOR attacks                 |

### Performance

| Practice                      | Details                                                         |
| ----------------------------- | --------------------------------------------------------------- |
| **Fully async I/O**           | `asyncpg` + `async/await` — no thread blocking                  |
| **Connection pooling**        | SQLAlchemy async engine manages connection pool                 |
| **Lazy-loaded relationships** | `selectin` loading strategy — avoids N+1 queries                |
| **Indexed columns**           | Foreign keys indexed for join performance                       |
| **Stateless auth**            | JWT — no database lookup on every request (except user refresh) |

### Code Quality

| Practice                      | Details                                                  |
| ----------------------------- | -------------------------------------------------------- |
| **Type safety (both stacks)** | Python type hints + TypeScript strict mode               |
| **Comprehensive test suite**  | 70 backend tests + 42 frontend tests                     |
| **Isolated test environment** | SQLite in-memory for backend; mocked fetch for frontend  |
| **Service mocking**           | LLM calls mocked in tests to avoid external dependencies |
| **Schema validation**         | Pydantic models auto-generate OpenAPI documentation      |

### Frontend-Specific

| Practice               | Details                                                |
| ---------------------- | ------------------------------------------------------ |
| **Protected routes**   | `ProtectedRoute` redirects to login if unauthenticated |
| **Public route guard** | `PublicRoute` redirects authenticated users to chat    |
| **Loading states**     | Auth loading flag prevents flash of wrong content      |
| **Optimistic UI**      | Thread list updates immediately on rename/delete       |
| **Error handling**     | User-facing error messages on API failures             |
| **Markdown rendering** | Assistant responses rendered with GFM support          |
| **Accessible forms**   | Proper `type`, `required`, `minLength` attributes      |

### LLM Integration

| Practice                   | Details                                                           |
| -------------------------- | ----------------------------------------------------------------- |
| **Proxy pattern**          | LiteLLM proxy centralizes model access, billing, rate limiting    |
| **Structured prompts**     | LangChain `ChatPromptTemplate` for maintainable prompts           |
| **Graceful fallbacks**     | Thread name generation falls back to first 5 words on LLM failure |
| **Error wrapping**         | `LLMServiceError` provides clean error propagation to HTTP layer  |
| **Spend tracking headers** | User ID, department, environment sent with every LLM request      |

---

## 11. Testing Strategy

### Backend Tests (pytest + pytest-asyncio)

```
tests/
├── conftest.py              # Shared fixtures (SQLite in-memory, test user, auth headers)
├── test_auth_service.py     # Unit tests for AuthService
├── test_thread_service.py   # Unit tests for ThreadService
├── test_message_service.py  # Unit tests for MessageService
├── test_chat_service.py     # Unit tests for ChatService (mocked LLM)
├── test_auth_routes.py      # Integration tests for /api/auth/*
├── test_thread_routes.py    # Integration tests for /api/threads/*
├── test_chat_routes.py      # Integration tests for /api/chat/*
└── test_health.py           # Health endpoint test
```

**Test Infrastructure:**

- SQLite in-memory database (fast, isolated per test)
- `httpx.AsyncClient` with ASGI transport (no network calls)
- Dependency override for DB session injection
- Mocked LLM service (no external API calls in tests)

**Run:** `pytest tests/ -v`

### Frontend Tests (Vitest + Testing Library)

```
src/test/
├── setup.ts                 # Test environment setup (localStorage mock, env vars)
├── AuthContext.test.tsx     # Context state management tests
├── chatApi.test.ts          # API service function tests (mocked fetch)
├── ChatComposer.test.tsx    # Component interaction tests
├── ChatMessageList.test.tsx # Rendering & markdown tests
├── ThreadSidebar.test.tsx   # Thread list interaction tests
└── LoginPage.test.tsx       # Form submission & OAuth tests
```

**Test Infrastructure:**

- jsdom environment for DOM simulation
- `@testing-library/react` for component testing
- `vi.mock()` for module mocking
- `vi.stubGlobal("fetch", ...)` for API mocking

**Run:** `npm run test:run`

---

## 12. Development Workflow

### Prerequisites

```bash
# Backend
Python 3.14+
pip install -r requirements.txt

# Frontend
Node.js 20+
npm install
```

### Environment Setup

**Backend `.env`:**

```env
LITELLM_PROXY_URL=http://litellm.amzur.com:4000
LITELLM_VIRTUAL_KEY=<your-key>
DATABASE_URL=postgresql+asyncpg://<connection-string>
JWT_SECRET=<random-secret>
GOOGLE_CLIENT_ID=<your-google-client-id>
```

**Frontend `.env`:**

```env
VITE_API_BASE_URL=http://localhost:8080
VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
```

### Running Locally

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Terminal 2: Frontend
cd front-end
npm run dev
```

### Running Tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd front-end
npm run test:run
```

### API Documentation

FastAPI auto-generates interactive docs:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

---

_Generated for AI Forge Chatbot v0.2.0_

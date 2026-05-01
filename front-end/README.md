# AI Forge Chatbot

Simple full-stack AI chatbot using:

- Frontend: React + TypeScript + Tailwind CSS (Vite)
- Backend: FastAPI (Python 3.11+)
- AI: LangChain LCEL with Gemini

## Folder Structure

```text
ai_forge_chatbot/
	backend/
		app/
			api/routes/chat.py
			core/config.py
			models/chat.py
			prompts/chat_prompt.py
			services/chat_service.py
			main.py
		.env.example
		requirements.txt
	src/
		components/
			ChatComposer.tsx
			ChatMessageList.tsx
		services/
			chatApi.ts
		types/
			chat.ts
		App.tsx
		index.css
		main.tsx
	.env.example
```

## Backend Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Create env file from template:

```bash
copy backend\.env.example backend\.env
```

4. Set `GEMINI_API_KEY` in `backend/.env`.
5. Run backend:

```bash
uvicorn app.main:app --reload --app-dir backend
```

Backend API:

- `POST /api/chat`
- `GET /health`

## Frontend Setup

1. Install dependencies:

```bash
npm install
```

2. Create frontend env file:

```bash
copy .env.example .env
```

3. Run frontend:

```bash
npm run dev
```

Frontend default URL: `http://localhost:5173`

## Notes

- Chat route is async and keeps LLM logic in a dedicated service layer.
- LangChain chain uses LCEL composition: `prompt | llm | parser`.
- Prompt template is in a separate module under `backend/app/prompts`.
- Basic LLM error handling returns `502` with readable details.

# EduVerse Backend

This folder contains the Day 0, Day 1, and Day 2 backend setup for EduVerse.

## Prerequisites

- Python 3.12 (already pinned in `.python-version`)
- `uv` installed

## Day 0 Setup

1. Install dependencies:

	```powershell
	uv sync --dev
	```

2. Create local environment file:

	```powershell
	Copy-Item .env.example .env
	```

3. Run the API:

	```powershell
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
	```

4. Health check:

	```powershell
	Invoke-RestMethod http://127.0.0.1:8000/health
	```

Expected response:

```json
{"status":"ok"}
```

## Day 1 Auth + Token Storage

- Protected endpoint: `POST /api/store-tokens`
- Protected endpoint: `GET /auth/status`
- Protected endpoint: `DELETE /auth/disconnect`
- Protected endpoint: `GET /courses`
- JWT middleware enforces `Authorization: Bearer <token>` on non-public routes.
- OAuth tokens are encrypted with Fernet before being stored in MongoDB.
- App startup validates MongoDB connectivity and ensures a unique `user_id` index on `oauth_tokens`.

Expected `POST /api/store-tokens` payload:

```json
{
	"email": "student@example.com",
	"access_token": "<google_access_token>",
	"refresh_token": "<google_refresh_token>",
	"token_expiry": "2026-04-09T19:05:00Z"
}
```

## Day 2 Ingestion + Classroom Loader

- Protected endpoint: `POST /ingest`
- Protected endpoint: `DELETE /cache/{course_id}`
- Ingestion uses `langchain_google_classroom.GoogleClassroomLoader` with per-user OAuth credentials.
- Parent-child chunking is implemented with `langchain_text_splitters`.
- Child chunk embeddings are stored through `langchain_mongodb.MongoDBAtlasVectorSearch`.
- Dedup state is tracked by LangChain Indexing API (`SQLRecordManager`).

Expected `POST /ingest` payload:

```json
{
	"course_id": "123456789",
	"force_refresh": false
}
```

`force_refresh=true` clears existing child/parent chunks for that user+course before re-ingesting.

Required Day 2 environment keys in `.env`:

- `NOMIC_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URL`
- `MONGO_URI`
- `MONGO_DB_NAME`

Required Google OAuth scopes for course ingestion:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/classroom.courses.readonly`
- `https://www.googleapis.com/auth/classroom.coursework.me.readonly`
- `https://www.googleapis.com/auth/classroom.announcements.readonly`
- `https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly`
- `https://www.googleapis.com/auth/drive.readonly`

If your frontend OAuth request omits these scopes, `/ingest` can fail with permission errors.

For local OAuth verification scripts, ensure `GOOGLE_REDIRECT_URL` exactly matches an authorized redirect URI in Google Cloud Console. A mismatch causes `Error 400: redirect_uri_mismatch`.

Optional (for attachment image parsing):

- Groq-first path:
	- `GROQ_API_KEY`
	- `GROQ_VISION_ENABLED` (default `true`)
	- `GROQ_VISION_MODEL`
	- `GROQ_VISION_TEMPERATURE`
	- `GROQ_VISION_MAX_TOKENS`
- Google Gemini fallback path:
	- `GOOGLE_API_KEY`

Vision selection behavior:

- If `GROQ_VISION_ENABLED=true` and `GROQ_API_KEY` is set, ingestion uses Groq vision.
- Otherwise, if `GOOGLE_API_KEY` is set, ingestion falls back to Gemini.
- If neither provider is configured, ingestion still runs and skips image parsing.

Create baseline indexes:

```powershell
uv run python scripts/setup_indexes.py
```

If you need pip-style setup:

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run tests:

```powershell
uv run pytest
```

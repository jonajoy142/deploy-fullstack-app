# Deploy Lab Fullstack

A small production-shaped app for testing the GitHub Output Service deployment flow end to end.

## Shape

- `frontend/` - Vite + React dashboard
- `backend/` - FastAPI API
- Database - PostgreSQL when `DATABASE_URL` is provided, local SQLite fallback when it is not

## Local Run

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Set `frontend/.env.local` if the backend is not on `http://localhost:8001`:

```env
VITE_API_URL=http://localhost:8001
```

## Deployment Test Payload

After pushing this folder to GitHub, use a deployment request like:

```json
{
  "project_id": "<registered-project-id>",
  "github_repo_url": "https://github.com/<owner>/<repo>",
  "github_branch": "main",
  "frontend_root": "frontend/",
  "backend_root": "backend/",
  "backend_provider": "railway",
  "db_type": "postgres"
}
```

The deployment scanner should also detect the roots and database type automatically.

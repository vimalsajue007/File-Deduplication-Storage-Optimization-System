# Intelligent File Deduplication & Storage Optimization

Upload files, find the ones that are **identical inside** (whatever they are called), see how much
space you can reclaim, and delete the redundant copies safely.

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Celery, Redis, JWT |
| Frontend | React 18 + Vite, TypeScript, Material UI, Axios, React Router, Chart.js — burgundy glass theme |
| Database | MySQL 8.0 |
| Ops | Docker & Docker Compose, Swagger/OpenAPI, Postman collection |

---

## 1. Quick start (Docker)

```bash
cp .env.example .env

docker compose up --build
```

| What | URL |
|---|---|
| Web app | http://localhost:3000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| MySQL Workbench | host `127.0.0.1`, port `3307`, user/password from `.env` |

Create an account on the sign-in page, upload files (try the same file twice under different names),
and watch the dashboard. The `backend` container applies Alembic migrations on start-up; the `worker`
container runs Celery.

## 2. Local development (without Docker for the apps)

```bash
# Infrastructure only
docker compose up -d mysql redis

# Backend  (Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO      

# Frontend
cd frontend
npm install
npm run dev                    # http://localhost:5173 (proxies /api to localhost:8000)
```

No Redis handy? Set `CELERY_TASK_ALWAYS_EAGER=true` and hashing runs inline (fine for small files).

## 3. Tests

```bash
cd backend
pytest
```

61 tests, no MySQL or Redis required (in-memory SQLite + inline Celery). They cover hashing
(chunk-size independence, streaming of a 24 MB file), the pure duplicate rules, the database
workflow (grouping, original election, group dissolution, idempotency, per-user isolation, re-scan),
upload validation, and the full API flow (auth, lockout, upload → dedupe → analytics → safe delete).

---

## 4. How duplicate detection works

1. **Upload** (`POST /files/upload`): each file is validated, streamed to disk in 1 MB chunks under a
   random name, and saved with `status = pending`. The API answers immediately (`202`).
2. **Celery task** `files.process_file` streams the file through **SHA-256** in 4 MB chunks (one
   reusable buffer — memory use does not grow with file size) and stores the digest in `file_hashes`.
3. **Grouping**: files of the *same user* with the same digest **and** size are duplicates. Name,
   upload time and location are irrelevant. A group exists only while it has 2+ files.
4. **Original** = earliest upload (lowest id on ties). Everything else is a duplicate.

| Term | Definition |
|---|---|
| Duplicate files | redundant copies (all group members except each original) |
| Duplicate storage | storage used by *every* file in a duplicate group (originals + copies) |
| Potential savings | storage used by the redundant copies = `size × (count − 1)` per group |

Concurrency: groups have a unique `(owner_id, content_hash)` constraint; if two workers race to
create the same group, one retries. Re-processing a file is idempotent.

## 5. Requirements checklist

| Requirement | Where |
|---|---|
| Upload / download / delete / search / filter / metadata | `api/routes/files.py`, `FilesPage.tsx` |
| Content hash, different names/times/locations still match | `services/hashing.py`, `services/dedupe.py` |
| Duplicate groups: original, duplicates, size, date, storage, savings | `api/routes/duplicates.py`, `DuplicatesPage.tsx` |
| Dashboard: totals, duplicate files/storage, savings, largest, recent | `api/routes/analytics.py`, `Dashboard.tsx` |
| Async hashing with Celery + Redis, API never blocks | `tasks/`, `docker-compose.yml` (`worker`) |
| Confirm, storage impact, protected files, deletion history | `POST /files/deletion-preview`, `bulk-delete`, `ConfirmDeleteDialog.tsx`, `deletion_history` |
| Filename / type / size / duplicate / date filters, pagination, sorting | `GET /files` query params |
| 7 tables | `users, files, file_hashes, duplicate_groups, file_metadata, deletion_history, audit_logs` (`models.py`, migration `0001`) |
| Large files, no full load into memory | chunked copy + chunked hashing; 4 MB / 1 MB chunk sizes configurable |
| Secure file validation | `services/validation.py` (below) |
| Prevent unauthorized access | JWT on every route; every query filters by owner; foreign ids return `404` |
| Config via environment variables | `core/config.py`, `.env.example` |
| Exception handling + logging | `core/exceptions.py`, `core/logging.py`, request-log middleware, audit log |
| Unit tests for duplicate logic | `tests/test_dedupe_logic.py`, `test_dedupe_service.py`, `test_hashing.py` |
| Swagger, Postman, README, `.env.example`, Docker, migrations | included |

### Security measures
* **Validation**: filename sanitised (path components, control and reserved characters removed; Unicode names kept);
  extension blocklist (`BLOCKED_EXTENSIONS`); magic-byte inspection rejects Windows/ELF/Mach-O executables
  whatever the name says, and rejects a `.png` that is really a PDF; empty files and files over
  `MAX_UPLOAD_SIZE_MB` are refused; request bodies above the limit are refused before parsing.
* **Storage**: random on-disk names, path-traversal guard, files served only as `attachment` with `nosniff`.
* **Auth**: bcrypt (with SHA-256 pre-hash, so long passwords are not truncated), JWT, constant-time-ish login,
  lock-out after repeated failures (`LOGIN_MAX_FAILED_ATTEMPTS`), production start-up refuses a weak `JWT_SECRET_KEY`.
* **Isolation**: duplicates are only ever matched within one user's files, so hash probing cannot reveal what others store.
* **Deletion**: `confirm=true` required, protected files rejected with `403`, bytes removed from disk only after the DB commit,
  every deletion written to `deletion_history` and `audit_logs`.

## 6. API overview (prefix `/api/v1`)

| Method & path | Purpose |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | accounts (login is the OAuth2 password form; username accepts email or username) |
| `POST /files/upload` | upload one or many (`multipart`, field `files`) |
| `GET /files` | search/filter/sort/paginate: `q, file_type, extension, min_size, max_size, duplicates, uploaded_from, uploaded_to, status, sort_by, sort_order, page, page_size` |
| `GET /files/{id}` · `GET /files/{id}/download` | details + metadata · download |
| `PATCH /files/{id}/protection` | protect / unprotect |
| `POST /files/deletion-preview` · `POST /files/bulk-delete` · `DELETE /files/{id}?confirm=true` | safe deletion |
| `GET /duplicates/groups` · `GET /duplicates/groups/{id}` | duplicate groups |
| `POST /duplicates/groups/{id}/cleanup` · `POST /duplicates/rescan` | keep original, delete the rest · full re-scan |
| `GET /analytics/summary` | dashboard data |
| `GET /history/deletions` · `GET /history/audit` | history |
| `GET /health` | liveness + DB check |

Import `postman/Dedupe_API.postman_collection.json`: run **Register**, then **Login** (the token is saved automatically).
Errors always look like `{"error": {"code", "message", "details"}}`.

## 7. Project layout

```
backend/app/{core,db,api/routes,services,tasks}   FastAPI app, models.py, schemas.py
backend/alembic/versions/0001_initial_schema.py   migration
backend/tests/                                    pytest suite
frontend/src/{api,components,context,pages}       React app (theme.ts + index.css = burgundy glass system)
postman/  docker-compose.yml  .env.example
```

## 8. Operational notes

* **Scaling**: add workers with `docker compose up --scale worker=4`. Uploads live on the `uploads_data` volume,
  which the API and workers share — use shared storage (NFS/EFS/S3-backed) if you run them on different hosts.
* **Uploads**: Starlette spools multipart bodies to a temp file before the route runs, so memory stays flat
  but each upload is written to disk twice. For multi-GB workloads consider direct-to-object-storage uploads.
* **Behind a proxy**: set `TRUST_PROXY_HEADERS=true` only when a trusted proxy sets `X-Forwarded-For`.
* **Backups**: back up both the MySQL volume and the uploads volume; they must be restored together.
* **Production**: set `ENVIRONMENT=production`, a 32+ character `JWT_SECRET_KEY`, restrict `CORS_ORIGINS`,
  put TLS in front of nginx, and consider `ALLOW_REGISTRATION=false`.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| Files stay on "Queued" | worker not running or Redis unreachable: `docker compose logs worker redis` |
| `413` on upload | raise `MAX_UPLOAD_SIZE_MB` (and nginx `client_max_body_size` if you changed it) |
| Backend exits at start with a `JWT_SECRET_KEY` error | you set `ENVIRONMENT=production` with the default secret |
| Re-scan button says worker unavailable | Redis/Celery down; the upload itself still succeeded |

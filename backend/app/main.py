import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import analytics, auth, duplicates, files, history
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import engine
from app.services.storage import upload_root

settings = get_settings()
logger = logging.getLogger("app.request")

TAGS = [
    {"name": "Authentication", "description": "Register, sign in and inspect the current user (JWT)."},
    {"name": "Files", "description": "Upload, download, search, filter, protect and safely delete files."},
    {"name": "Duplicates", "description": "Duplicate groups, storage savings and clean-up."},
    {"name": "Analytics", "description": "Dashboard statistics."},
    {"name": "History & Audit", "description": "Deletion history and audit trail."},
]

DESCRIPTION = """
Detects files with **identical content** (SHA-256) regardless of filename, upload time or
location, groups them, and shows how much storage could be reclaimed.

* Hashing runs in **Celery workers**; uploads return immediately with `status: pending`.
* Duplicate detection is **per user** — nobody can see or match against another user's files.
* Deleting requires `confirm=true`, is blocked for **protected** files and is recorded in the deletion history.

Click **Authorize** and sign in with your email (or username) and password to try the endpoints.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    upload_root()
    logging.getLogger(__name__).info("Started in %s mode", settings.ENVIRONMENT)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description=DESCRIPTION,
        version="1.0.0",
        openapi_tags=TAGS,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    max_request = settings.max_upload_bytes * settings.MAX_FILES_PER_UPLOAD + 1024 * 1024

    @app.middleware("http")
    async def guard_and_log(request: Request, call_next):
        started = time.perf_counter()
        # Reject absurdly large bodies before any parsing happens.
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_request:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "request_too_large", "message": "The request is too large.", "details": None}},
            )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        logger.info(
            "%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    prefix = settings.API_PREFIX
    for module in (auth, files, duplicates, analytics, history):
        app.include_router(module.router, prefix=prefix)

    @app.get("/health", tags=["Health"], summary="Liveness and database check")
    def health():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Health check failed")
            return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
        return {"status": "ok", "database": "up"}

    return app


app = create_app()

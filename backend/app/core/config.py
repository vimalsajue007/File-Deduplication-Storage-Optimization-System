"""Application settings, loaded from environment variables (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    # --- General -----------------------------------------------------------
    APP_NAME: str = "Intelligent File Deduplication"
    ENVIRONMENT: str = "development"  # development | production
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ALLOW_REGISTRATION: bool = True
    TRUST_PROXY_HEADERS: bool = False

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str | None = None  # overrides MYSQL_* when set (used by tests)
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "dedupe"
    MYSQL_PASSWORD: str = "dedupe_password"
    MYSQL_DATABASE: str = "dedupe_db"

    # --- Redis / Celery ----------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_ALWAYS_EAGER: bool = False  # run tasks inline (tests / no-Redis dev)

    # --- Auth --------------------------------------------------------------
    JWT_SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # --- Files -------------------------------------------------------------
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 1024
    MAX_FILES_PER_UPLOAD: int = 20
    HASH_CHUNK_SIZE_KB: int = 4096
    COPY_CHUNK_SIZE_KB: int = 1024
    BLOCKED_EXTENSIONS: str = (
        "exe,dll,bat,cmd,com,msi,scr,pif,cpl,vbs,vbe,wsf,jar,apk,app,ps1,reg,lnk,hta"
    )

    @model_validator(mode="after")
    def _check_production_secret(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production" and (
            self.JWT_SECRET_KEY == INSECURE_DEFAULT_SECRET or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError("JWT_SECRET_KEY must be a random string of 32+ characters in production")
        return self

    # --- Derived values ----------------------------------------------------
    @property
    def sqlalchemy_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{quote_plus(self.MYSQL_USER)}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def blocked_extensions_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower().lstrip(".") for e in self.BLOCKED_EXTENSIONS.split(",") if e.strip())

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def hash_chunk_bytes(self) -> int:
        return self.HASH_CHUNK_SIZE_KB * 1024

    @property
    def copy_chunk_bytes(self) -> int:
        return self.COPY_CHUNK_SIZE_KB * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

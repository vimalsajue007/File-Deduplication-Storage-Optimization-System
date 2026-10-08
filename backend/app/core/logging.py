"""Logging configuration: console + rotating file (when the log dir is writable)."""
from __future__ import annotations

import logging
import logging.config
import logging.handlers  # noqa: F401  (needed by dictConfig)
from pathlib import Path

from app.core.config import get_settings

_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def setup_logging() -> None:
    settings = get_settings()
    handlers: dict[str, dict] = {
        "console": {"class": "logging.StreamHandler", "formatter": "default", "level": settings.LOG_LEVEL}
    }
    try:
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "default",
            "level": settings.LOG_LEVEL,
        }
    except OSError:  # read-only filesystem etc. -> console only
        pass

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": _FORMAT}},
            "handlers": handlers,
            "root": {"level": settings.LOG_LEVEL, "handlers": list(handlers)},
            "loggers": {"uvicorn.access": {"level": "WARNING"}},  # requests are logged by our middleware
        }
    )

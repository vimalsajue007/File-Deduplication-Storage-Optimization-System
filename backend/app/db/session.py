from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # In-memory SQLite is only used by the test-suite.
        return create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    return create_engine(
        url,
        pool_pre_ping=True,   # transparently replace dead connections
        pool_recycle=1800,    # MySQL closes idle connections after wait_timeout
        pool_size=10,
        max_overflow=20,
    )


engine = make_engine(get_settings().sqlalchemy_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

"""Database engine and session helpers for the fraud-operations API."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from fraud_detection.config import PROJECT_ROOT


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_database_url() -> str:
    default_path = PROJECT_ROOT / "data" / "interim" / "fraud_ops.db"
    url = os.getenv("DATABASE_URL", f"sqlite:///{default_path}")
    return _normalize_database_url(url)


class Base(DeclarativeBase):
    """Declarative base for database models."""


def create_db_engine(database_url: str | None = None):
    url = _normalize_database_url(database_url or get_database_url())
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


def create_session_factory(database_url: str | None = None):
    engine = create_db_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:"):
        return
    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:":
        return
    normalized = database[1:] if database.startswith("/") and len(database) > 2 and database[2] == ":" else database
    Path(normalized).parent.mkdir(parents=True, exist_ok=True)

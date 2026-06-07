"""Database configuration and session helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base


def _is_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _sqlite_file_path(database_url: str) -> Path | None:
    if not _is_sqlite(database_url):
        return None
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw_path = database_url[len(prefix) :]
    return Path(raw_path)


def _legacy_sqlite_backup_path(database_path: Path) -> Path:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return database_path.with_name(f"{database_path.stem}.legacy-{timestamp}{database_path.suffix}")


def _looks_like_legacy_local_sqlite_schema(database_url: str) -> bool:
    database_path = _sqlite_file_path(database_url)
    if database_path is None or not database_path.exists():
        return False

    engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False})
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "users" not in table_names or "alembic_version" in table_names:
            return False

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        return "password_hash" not in user_columns
    finally:
        engine.dispose()


def _backup_legacy_sqlite_database(database_url: str) -> Path | None:
    database_path = _sqlite_file_path(database_url)
    if database_path is None or not database_path.exists():
        return None

    backup_path = _legacy_sqlite_backup_path(database_path)
    dispose_engine(database_url)
    database_path.replace(backup_path)
    return backup_path


def _ensure_sqlite_column(
    database_url: str,
    table_name: str,
    column_name: str,
    column_ddl: str,
) -> None:
    if not _is_sqlite(database_url):
        return

    engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False})
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if table_name not in table_names:
            return

        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name in column_names:
            return

        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}"))
    finally:
        engine.dispose()


def _reconcile_local_sqlite_schema(database_url: str) -> None:
    # Keep local SQLite databases usable across additive model changes.
    _ensure_sqlite_column(
        database_url,
        table_name="scored_cases",
        column_name="latest_gemini_analysis_payload",
        column_ddl="JSON NULL",
    )


@lru_cache
def get_engine(database_url: str | None = None):
    resolved_url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if _is_sqlite(resolved_url) else {}
    return create_engine(resolved_url, future=True, connect_args=connect_args)


@lru_cache
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(database_url: str | None = None) -> None:
    resolved_url = database_url or get_settings().database_url
    if _looks_like_legacy_local_sqlite_schema(resolved_url):
        _backup_legacy_sqlite_database(resolved_url)

    Base.metadata.create_all(bind=get_engine(resolved_url))
    _reconcile_local_sqlite_schema(resolved_url)


def dispose_engine(database_url: str | None = None) -> None:
    get_engine(database_url).dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()

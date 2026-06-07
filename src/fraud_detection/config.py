"""Project-wide configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def default_database_url() -> str:
    local_path = DATA_DIR / "interim" / "fraud_ops.db"
    return f"sqlite:///{local_path.as_posix()}"


@dataclass(frozen=True)
class Settings:
    database_url: str
    auth_secret: str
    auth_token_ttl_seconds: int
    bootstrap_history: bool
    cors_allowed_origins: tuple[str, ...]
    analyst_username: str
    analyst_password: str
    manager_username: str
    manager_password: str
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", default_database_url()),
        auth_secret=os.getenv("AUTH_SECRET", "dev-only-change-me"),
        auth_token_ttl_seconds=int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "28800")),
        bootstrap_history=_env_bool("BOOTSTRAP_HISTORY", True),
        cors_allowed_origins=_env_csv("CORS_ALLOWED_ORIGINS", ("http://localhost:3000",)),
        analyst_username=os.getenv("ANALYST_USERNAME", "analyst"),
        analyst_password=os.getenv("ANALYST_PASSWORD", "changeme-analyst"),
        manager_username=os.getenv("MANAGER_USERNAME", "admin"),
        manager_password=os.getenv("MANAGER_PASSWORD", "changeme-admin"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        gemini_timeout_seconds=int(os.getenv("GEMINI_TIMEOUT_SECONDS", "15")),
    )

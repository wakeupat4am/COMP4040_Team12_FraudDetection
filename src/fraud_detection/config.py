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
DOTENV_PATH = PROJECT_ROOT / ".env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_env_file(DOTENV_PATH)

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
    clerk_jwt_key: str | None
    clerk_jwt_algorithms: tuple[str, ...]
    clerk_issuer: str | None
    clerk_audience: str | None
    bootstrap_history: bool
    cors_allowed_origins: tuple[str, ...]
    analyst_username: str
    analyst_clerk_user_id: str | None
    manager_username: str
    manager_clerk_user_id: str | None
    mlflow_enabled: bool
    mlflow_tracking_uri: str
    mlflow_experiment_name: str
    mlflow_model_run_id: str | None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", default_database_url()),
        clerk_jwt_key=os.getenv("CLERK_JWT_KEY") or os.getenv("CLERK_PEM_PUBLIC_KEY"),
        clerk_jwt_algorithms=_env_csv("CLERK_JWT_ALGORITHMS", ("RS256",)),
        clerk_issuer=os.getenv("CLERK_ISSUER"),
        clerk_audience=os.getenv("CLERK_AUDIENCE"),
        bootstrap_history=_env_bool("BOOTSTRAP_HISTORY", True),
        cors_allowed_origins=_env_csv("CORS_ALLOWED_ORIGINS", ("http://localhost:3000",)),
        analyst_username=os.getenv("ANALYST_USERNAME", "analyst"),
        analyst_clerk_user_id=os.getenv("ANALYST_CLERK_USER_ID"),
        manager_username=os.getenv("MANAGER_USERNAME", "admin"),
        manager_clerk_user_id=os.getenv("MANAGER_CLERK_USER_ID"),
        mlflow_enabled=_env_bool("MLFLOW_ENABLED", False),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "file:///tmp/fraud-detection-mlruns"),
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "fraud-detection-production"),
        mlflow_model_run_id=os.getenv("MLFLOW_MODEL_RUN_ID"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        gemini_timeout_seconds=int(os.getenv("GEMINI_TIMEOUT_SECONDS", "15")),
    )

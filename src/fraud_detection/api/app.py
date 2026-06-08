"""FastAPI application factory for the production backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from time import sleep
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from ..config import Settings, get_settings
from ..database import dispose_engine, init_db
from ..services import GeminiAdvisoryService
from .routes import router

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


def create_app(
    settings: Settings | None = None,
    runtime: ProductionScoringRuntime | None = None,
    gemini_advisor: GeminiAdvisoryService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for attempt in range(1, 11):
            try:
                init_db(app.state.settings.database_url)
                break
            except OperationalError as exc:
                if attempt == 10:
                    raise
                sleep(2)

        try:
            yield
        finally:
            dispose_engine(app.state.settings.database_url)

    app = FastAPI(
        title="Fraud Analyst Backend",
        version="1.0.0",
        description="Backend-first fraud scoring, analyst queue, and review workflow service.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.runtime = runtime
    app.state.gemini_advisor = gemini_advisor
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app.state.settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    return app


app = create_app()

"""FastAPI application factory for the production backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import Settings, get_settings
from ..database import dispose_engine, get_session_factory, init_db
from ..services import AuthService
from .routes import router

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


def create_app(settings: Settings | None = None, runtime: ProductionScoringRuntime | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(app.state.settings.database_url)
        session = get_session_factory(app.state.settings.database_url)()
        try:
            auth_service = AuthService(session=session, settings=app.state.settings)
            auth_service.bootstrap_users()
            session.commit()
        finally:
            session.close()

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

"""FastAPI application factory for the production backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import Settings, get_settings
from ..database import dispose_engine, get_session_factory, init_db
from ..services import AuthService, GeminiAdvisoryService
from .routes import router

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


def create_app(
    settings: Settings | None = None,
    runtime: ProductionScoringRuntime | None = None,
    gemini_advisor: GeminiAdvisoryService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Fraud Analyst Backend",
        version="1.0.0",
        description="Backend-first fraud scoring, analyst queue, and review workflow service.",
    )
    app.state.settings = settings or get_settings()
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

    @app.on_event("startup")
    def _startup() -> None:
        init_db(app.state.settings.database_url)
        session = get_session_factory(app.state.settings.database_url)()
        try:
            auth_service = AuthService(session=session, settings=app.state.settings)
            auth_service.bootstrap_users()
            session.commit()
        finally:
            session.close()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        dispose_engine(app.state.settings.database_url)

    return app


app = create_app()

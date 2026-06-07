"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..auth import decode_access_token
from ..config import Settings
from ..database import get_session_factory
from ..models import User
from ..repositories import UserRepository
from ..services import AuthService, CaseService, GeminiAdvisoryService

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_runtime_dependency(request: Request):
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is not None:
        return runtime
    from ..runtime import get_runtime

    return get_runtime()


def get_gemini_advisor_dependency(request: Request) -> GeminiAdvisoryService:
    gemini_advisor = getattr(request.app.state, "gemini_advisor", None)
    if gemini_advisor is not None:
        return gemini_advisor
    return GeminiAdvisoryService.from_settings(request.app.state.settings)


def get_db_session(request: Request):
    session = get_session_factory(request.app.state.settings.database_url)()
    try:
        yield session
    finally:
        session.close()


def get_auth_service(
    request: Request,
    session: Session = Depends(get_db_session),
) -> AuthService:
    return AuthService(session=session, settings=request.app.state.settings)


def get_case_service(
    request: Request,
    session: Session = Depends(get_db_session),
) -> CaseService:
    return CaseService(
        session=session,
        runtime=get_runtime_dependency(request),
        gemini_advisor=get_gemini_advisor_dependency(request),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials, settings.auth_secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = UserRepository().get_by_username(session, str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency

"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..auth import decode_clerk_token
from ..config import Settings
from ..database import get_session_factory
from ..models import User
from ..repositories import UserRepository
from ..services import AuthService, CaseService

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


bearer_scheme = HTTPBearer(auto_error=False)


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_runtime_dependency(request: Request):
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is not None:
        return runtime
    from ..runtime import get_runtime

    return get_runtime()


async def get_db_session(request: Request):
    session = get_session_factory(request.app.state.settings.database_url)()
    try:
        yield session
    finally:
        session.close()


async def get_auth_service(
    request: Request,
    session: Session = Depends(get_db_session),
) -> AuthService:
    return AuthService(session=session, settings=request.app.state.settings)


async def get_case_service(
    request: Request,
    session: Session = Depends(get_db_session),
) -> CaseService:
    return CaseService(session=session, runtime=await get_runtime_dependency(request))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if settings.clerk_jwt_key is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clerk JWT verification is not configured")

    try:
        payload = decode_clerk_token(
            token=credentials.credentials,
            jwt_key=settings.clerk_jwt_key,
            algorithms=settings.clerk_jwt_algorithms,
            issuer=settings.clerk_issuer,
            audience=settings.clerk_audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    clerk_user_id = payload.get("sub")
    if not isinstance(clerk_user_id, str) or not clerk_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clerk token is missing a user subject")

    user = UserRepository().get_by_clerk_user_id(session, clerk_user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    user.last_login_at = datetime.now(tz=timezone.utc)
    session.commit()
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency

"""Authentication service for internal users."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..config import Settings
from ..models import User
from ..repositories import UserRepository, WorkflowRepository


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository()
        self.workflow = WorkflowRepository()

    def bootstrap_users(self) -> None:
        seeded = [
            (self.settings.analyst_username, self.settings.analyst_password, "analyst"),
            (self.settings.manager_username, self.settings.manager_password, "manager_admin"),
        ]
        for username, password, role in seeded:
            if self.users.get_by_username(self.session, username) is None:
                self.users.create(self.session, username=username, password_hash=hash_password(password), role=role)

    def authenticate(self, username: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_username(self.session, username)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")

        user.last_login_at = datetime.now(tz=timezone.utc)
        token = create_access_token(
            subject=user.username,
            role=user.role,
            secret=self.settings.auth_secret,
            ttl_seconds=self.settings.auth_token_ttl_seconds,
        )
        self.workflow.add_audit_log(
            self.session,
            transaction_id=None,
            action="auth_login",
            actor_user_id=user.id,
            details={"username": user.username, "role": user.role},
        )
        return user, token

"""Authentication service for Clerk-backed internal users."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import Settings
from ..repositories import UserRepository, WorkflowRepository


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository()
        self.workflow = WorkflowRepository()

    def bootstrap_users(self) -> None:
        seeded = [
            (self.settings.analyst_username, self.settings.analyst_clerk_user_id, "analyst"),
            (self.settings.manager_username, self.settings.manager_clerk_user_id, "manager_admin"),
        ]
        for username, clerk_user_id, role in seeded:
            if clerk_user_id:
                self.users.upsert_clerk_user(self.session, username=username, clerk_user_id=clerk_user_id, role=role)

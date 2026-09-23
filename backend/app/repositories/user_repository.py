"""Users, roles and the two profile tables hanging off a user."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GovernmentDepartment, Role, RoleName, Startup, User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    # -- users ------------------------------------------------------------

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        """
        Look up by email, case-insensitively.

        `AuthService` lower-cases before querying and every seeded address is
        already lower-case, but a `lower()` comparison means a legacy row with
        mixed case still authenticates rather than silently failing to log in.
        """
        return self.db.execute(
            select(User).where(func.lower(User.email) == email.strip().lower())
        ).scalars().one_or_none()

    def email_exists(self, email: str) -> bool:
        return self.db.execute(
            select(func.count()).select_from(User)
            .where(func.lower(User.email) == email.strip().lower())
        ).scalar_one() > 0

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()   # assign the server-side UUID without committing
        return user

    def list_all(self) -> list[User]:
        return list(self.db.execute(
            select(User).order_by(User.created_at.desc())).scalars())

    # -- roles ------------------------------------------------------------

    def get_role(self, name: RoleName) -> Role | None:
        return self.db.execute(
            select(Role).where(Role.name == name)).scalars().one_or_none()

    # -- profiles ---------------------------------------------------------

    def find_department_by_user(self, user_id: uuid.UUID) -> GovernmentDepartment | None:
        return self.db.execute(
            select(GovernmentDepartment).where(GovernmentDepartment.user_id == user_id)
        ).scalars().one_or_none()

    def find_startup_by_user(self, user_id: uuid.UUID) -> Startup | None:
        return self.db.execute(
            select(Startup).where(Startup.user_id == user_id)
        ).scalars().one_or_none()

    def add_department(self, department: GovernmentDepartment) -> GovernmentDepartment:
        self.db.add(department)
        self.db.flush()
        return department

    def add_startup(self, startup: Startup) -> Startup:
        self.db.add(startup)
        self.db.flush()
        return startup

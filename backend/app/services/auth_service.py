"""
Registration, login and the current-user lookup.

Port of Java's `AuthService`. Every guard, message and status code is
reproduced, because the frontend surfaces `message` verbatim:

* EXPERT/ADMIN self-registration -> 403
* duplicate email -> 409
* STARTUP without `companyName` / GOVERNMENT without `departmentName` -> 400
* unknown email or wrong password -> 401 "Invalid email or password"
* deactivated account -> 403

The unknown-email and wrong-password cases share one message on purpose: they
must be indistinguishable, or the endpoint becomes an account-enumeration
oracle.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import GovernmentDepartment, RoleName, Startup, User
from app.repositories import UserRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.security.jwt import create_access_token
from app.security.password import hash_password, verify_password
from app.services.audit_service import Action, AuditService

#: Java sets this explicitly on a self-registered startup rather than relying
#: on the column default, so it is set explicitly here too.
DEFAULT_READINESS_SCORE = Decimal("50")

#: Roles a person may create for themselves. Experts and admins are provisioned.
SELF_SERVICE_ROLES = (RoleName.STARTUP, RoleName.GOVERNMENT)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    # ------------------------------------------------------------------

    def register(self, request: RegisterRequest) -> AuthResponse:
        if request.role not in SELF_SERVICE_ROLES:
            raise ApiException.forbidden(
                "Admin and Expert accounts can only be provisioned by an administrator")

        email = request.email.strip().lower()
        if self.users.email_exists(email):
            raise ApiException.conflict("An account with this email already exists")

        if request.role is RoleName.STARTUP and not (request.company_name or "").strip():
            raise ApiException.bad_request(
                "companyName is required when registering as a startup")
        if request.role is RoleName.GOVERNMENT and not (request.department_name or "").strip():
            raise ApiException.bad_request(
                "departmentName is required when registering as a government department")

        role = self.users.get_role(request.role)
        if role is None:
            raise ApiException.not_found(f"Role not found: {request.role.value}")

        user = self.users.add(User(
            email=email,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
            role_id=role.id,
            is_active=True,
        ))

        if request.role is RoleName.STARTUP:
            self.users.add_startup(Startup(
                user_id=user.id,
                company_name=request.company_name,
                readiness_score=DEFAULT_READINESS_SCORE,
            ))
        else:
            self.users.add_department(GovernmentDepartment(
                user_id=user.id,
                department_name=request.department_name,
                ministry=request.ministry,
                region=request.region,
            ))

        self.audit.log(user, Action.REGISTER, "User", user.id,
                       {"role": role.name.value})
        self.db.commit()

        return AuthResponse(
            token=create_access_token(user.id, user.email, role.name.value),
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role.name,
        )

    # ------------------------------------------------------------------

    def login(self, request: LoginRequest) -> AuthResponse:
        user = self.users.find_by_email(request.email)

        # Verify against a real hash even when the account is unknown, so the
        # response time does not reveal whether the address exists.
        if user is None:
            hash_password(request.password)
            raise ApiException(401, "Invalid email or password")

        if not user.is_active:
            raise ApiException.forbidden("This account has been deactivated")

        if not verify_password(request.password, user.password_hash):
            raise ApiException(401, "Invalid email or password")

        self.audit.log(user, Action.LOGIN, "User", user.id)
        self.db.commit()

        role_name = user.role.name
        return AuthResponse(
            token=create_access_token(user.id, user.email, role_name.value),
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role_name,
        )

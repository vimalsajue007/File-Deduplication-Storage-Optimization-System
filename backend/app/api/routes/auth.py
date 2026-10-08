from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, ForbiddenError, TooManyRequestsError
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas import Token, UserCreate, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201, summary="Create an account")
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    if not settings.ALLOW_REGISTRATION:
        raise ForbiddenError("Registration is disabled on this server.")

    email = payload.email.lower()
    exists = db.scalar(
        select(User.id).where(or_(func.lower(User.email) == email, func.lower(User.username) == payload.username.lower()))
    )
    if exists:
        raise ConflictError("That email or username is already registered.")

    user = User(email=email, username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()
    audit.record(db, "auth.register", user_id=user.id, request=request, resource_type="user", resource_id=user.id)
    db.commit()
    return user


def _recent_failures(db: Session, identity: str) -> int:
    window = utcnow() - timedelta(minutes=get_settings().LOGIN_LOCKOUT_MINUTES)
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login_failed",
            AuditLog.resource_id == identity,
            AuditLog.created_at >= window,
        )
    ) or 0


@router.post("/login", response_model=Token, summary="Sign in (OAuth2 password flow)")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """`username` accepts either the account's email address or its username."""
    settings = get_settings()
    identity = form.username.strip().lower()[:255]

    if _recent_failures(db, identity) >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
        raise TooManyRequestsError(
            f"Too many failed sign-in attempts. Try again in {settings.LOGIN_LOCKOUT_MINUTES} minutes."
        )

    user = db.scalar(select(User).where(or_(func.lower(User.email) == identity, func.lower(User.username) == identity)))
    # Always run a hash comparison so response time doesn't reveal whether the account exists.
    password_ok = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)

    if not user or not password_ok or not user.is_active:
        audit.record(
            db, "auth.login_failed", user_id=user.id if user else None, request=request,
            resource_type="user", resource_id=identity, commit=True,
        )
        raise AuthenticationError("Incorrect email/username or password.")

    user.last_login_at = utcnow()
    audit.record(db, "auth.login", user_id=user.id, request=request, resource_type="user", resource_id=user.id)
    db.commit()
    token, expires_in = create_access_token(user.id)
    return Token(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current user")
def me(user: User = Depends(get_current_user)) -> User:
    return user

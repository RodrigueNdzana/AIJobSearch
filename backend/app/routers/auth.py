from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.database import get_db
from app.models.employer import Employer
from app.models.job_seeker import JobSeeker
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserRole
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, Token, UserRegister
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    if payload.role == UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin accounts cannot self-register")

    user = User(email=payload.email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    await db.flush()  # populate user.id before creating the extension row

    if payload.role == UserRole.job_seeker:
        db.add(JobSeeker(user_id=user.id, full_name=payload.full_name))
    elif payload.role == UserRole.employer:
        db.add(Employer(user_id=user.id, company_name=payload.full_name))

    await db.commit()

    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Always returns the same generic response whether or not the email exists,
    so this endpoint can't be used to enumerate registered accounts. If the
    account exists, a reset email is sent (or logged, if SMTP isn't configured
    — see app/services/email_service.py).

    Dev convenience: when SMTP isn't configured (settings.smtp_host is empty),
    the reset link is also returned directly in the response as
    `dev_reset_link`, so the flow is testable without digging through server
    logs. This intentionally trades a small amount of account-enumeration
    protection for usability, but only in the no-SMTP case — which is a
    deliberate local/dev configuration choice, never the production default.
    Once SMTP_HOST is set, this field disappears and the generic-response
    behavior is fully enforced.
    """
    generic_response = {"detail": "If an account with that email exists, a password reset link has been sent."}

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return generic_response

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes)

    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    reset_link = f"{settings.frontend_base_url}/reset-password.html?token={raw_token}"
    send_password_reset_email(user.email, reset_link)

    if not settings.smtp_host:
        return {**generic_response, "dev_reset_link": reset_link}

    return generic_response


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_reset_token(payload.token)

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None or reset_token.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has already been used")

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link has expired. Please request a new one")

    user = await db.get(User, reset_token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has already been used")

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = datetime.now(timezone.utc)
    await db.commit()

    return {"detail": "Password reset successfully. You can now log in with your new password."}

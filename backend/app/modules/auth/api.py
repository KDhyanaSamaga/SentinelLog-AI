"""
Authentication API endpoints.

All endpoints use ``APIRouter`` (not a separate ``FastAPI`` instance)
and are mounted under ``/api/v1/auth``.

Rate limits are applied to public endpoints (login, register,
password recovery) via the shared SlowAPI limiter.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limiter import limiter
from app.modules.auth.dependencies import get_current_principal
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    CurrentPrincipalResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterOrganizationRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.modules.auth.service import (
    AccountDisabledError,
    AuthenticationError,
    DuplicateEmailError,
    SessionExpiredError,
    TokenReplayError,
    authenticate_identity,
    change_password,
    issue_session,
    logout_all_sessions,
    logout_session,
    refresh_session,
    register_organization,
    request_password_reset,
    reset_password,
)
from app.modules.auth.types import AuthenticatedPrincipal
from app.modules.organization.schemas import OrganizationProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ═════════════════════════════════════════════════════════════════════
# POST /register
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/register",
    response_model=OrganizationProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization",
)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterOrganizationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public, rate-limited.  Creates a new organization account.
    """
    try:
        org = await register_organization(
            db,
            name=body.organization_name,
            email=body.organization_email,
            phone=body.organization_phone,
            password=body.password,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return OrganizationProfile(
        unique_id=org.id,
        organization_name=org.organization_name,
        organization_email=org.organization_email,
        organization_phone=org.organization_phone,
        is_active=org.is_active,
        is_verified=org.is_verified,
    )


# ═════════════════════════════════════════════════════════════════════
# POST /login
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain tokens",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public, rate-limited.  Returns access + refresh tokens.
    """
    try:
        principal = await authenticate_identity(
            db, body.email, body.password, body.identity_type,
        )
    except AccountDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    issued = await issue_session(
        db,
        principal,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        token_type=issued.token_type,
        expires_in=issued.expires_in,
    )


# ═════════════════════════════════════════════════════════════════════
# POST /refresh
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate the refresh token and issue a new access token.
    """
    try:
        issued = await refresh_session(db, body.refresh_token)
    except TokenReplayError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token replay detected. All sessions revoked.",
        )
    except (AuthenticationError, SessionExpiredError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    return TokenResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        token_type=issued.token_type,
        expires_in=issued.expires_in,
    )


# ═════════════════════════════════════════════════════════════════════
# POST /logout
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
)
async def logout(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated.  Revokes the caller's session."""
    if principal.session_id:
        await logout_session(db, principal.session_id)


# ═════════════════════════════════════════════════════════════════════
# POST /logout-all
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all sessions",
)
async def logout_all(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated.  Revokes every session for the identity."""
    await logout_all_sessions(db, principal)


# ═════════════════════════════════════════════════════════════════════
# GET /me
# ═════════════════════════════════════════════════════════════════════


@router.get(
    "/me",
    response_model=CurrentPrincipalResponse,
    summary="Get current identity",
)
async def me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Authenticated.  Returns the caller's safe profile."""
    return CurrentPrincipalResponse(
        identity_id=principal.identity_id,
        identity_type=principal.identity_type,
        organization_id=principal.organization_id,
        permissions=sorted(principal.permissions),
    )


# ═════════════════════════════════════════════════════════════════════
# POST /change-password
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
)
async def change_pwd(
    body: ChangePasswordRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticated.  Re-verifies current password, applies the new one,
    and revokes all existing sessions.
    """
    try:
        await change_password(
            db, principal, body.current_password, body.new_password,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


# ═════════════════════════════════════════════════════════════════════
# POST /forgot-password
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Request password reset",
)
@limiter.limit("3/minute")
async def forgot_pwd(
    request: Request,
    body: ForgotPasswordRequest,
):
    """
    Public, rate-limited.  Always returns 202 to prevent enumeration.
    """
    await request_password_reset(body.email)
    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent.",
    )


# ═════════════════════════════════════════════════════════════════════
# POST /reset-password
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset password with token",
)
async def reset_pwd(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete account recovery with a single-use reset token.
    """
    try:
        await reset_password(db, body.reset_token, body.new_password)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Password reset is not yet available.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

"""
Authentication service — core workflow orchestration.

This layer implements the complete authentication lifecycle:
registration, credential verification, session management,
token rotation, logout, and password changes.

It does not depend on FastAPI's ``Request`` object; that belongs
in the API layer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone as tz

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    constant_time_secret_match,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_password_rehash,
    validate_password_policy,
    verify_password,
)
from app.modules.admin.models import Admin
from app.modules.auth import repository as auth_repo
from app.modules.auth.types import (
    ADMIN_DEFAULT_PERMISSIONS,
    ORGANIZATION_DEFAULT_PERMISSIONS,
    AuthenticatedPrincipal,
    IssuedSession,
)
from app.modules.organization import repository as org_repo
from app.modules.organization.models import Organization

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Exceptions
# ═════════════════════════════════════════════════════════════════════


class AuthenticationError(Exception):
    """Raised when credentials are invalid or the account cannot log in."""


class AccountDisabledError(AuthenticationError):
    """Raised when the account is deactivated."""


class DuplicateEmailError(Exception):
    """Raised when registration is attempted with an existing email."""


class SessionExpiredError(Exception):
    """Raised when a session or refresh token has expired."""


class TokenReplayError(Exception):
    """Raised when refresh-token replay is detected."""


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_password_hash(identity: Organization | Admin) -> str:
    if isinstance(identity, Organization):
        return identity.organization_hashed_password
    return identity.admin_hashed_password


def _get_identity_email(identity: Organization | Admin) -> str:
    if isinstance(identity, Organization):
        return identity.organization_email
    return identity.admin_email


def _get_organization_id(identity: Organization | Admin) -> uuid.UUID:
    """Derive the organization UUID from the identity."""
    if isinstance(identity, Organization):
        return identity.id
    return identity.admin_organization_id


def _get_permissions(identity_type: str) -> frozenset[str]:
    if identity_type == "organization":
        return ORGANIZATION_DEFAULT_PERMISSIONS
    return ADMIN_DEFAULT_PERMISSIONS


def _build_principal(
    identity: Organization | Admin,
    identity_type: str,
    session_id: uuid.UUID | None = None,
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        identity_id=identity.id,
        identity_type=identity_type,
        organization_id=_get_organization_id(identity),
        permissions=_get_permissions(identity_type),
        session_id=session_id,
    )


# ═════════════════════════════════════════════════════════════════════
# Registration
# ═════════════════════════════════════════════════════════════════════


async def register_organization(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str,
    password: str,
) -> Organization:
    """
    Validate registration rules, hash password, and create an
    organization.

    Raises ``DuplicateEmailError`` if the email already exists.
    Raises ``ValueError`` if the password violates policy.
    """
    email = _normalize_email(email)

    # Check duplicate email
    existing = await org_repo.get_organization_by_email(db, email)
    if existing is not None:
        raise DuplicateEmailError("An account with this email already exists.")

    # Validate and hash password
    validate_password_policy(password)
    password_hash = hash_password(password)

    org = await org_repo.create_organization(
        db,
        name=name,
        email=email,
        phone=phone,
        password_hash=password_hash,
    )

    logger.info("Organization registered: %s", org.id)
    return org


# ═════════════════════════════════════════════════════════════════════
# Authentication
# ═════════════════════════════════════════════════════════════════════


async def authenticate_identity(
    db: AsyncSession,
    email: str,
    password: str,
    identity_type: str,
) -> AuthenticatedPrincipal:
    """
    Normalize identity, verify credentials, check account state.

    1. Normalize email.
    2. Find the identity.
    3. If missing, run verify against dummy hash to reduce timing leak.
    4. Verify password.
    5. Check is_active.
    6. Rehash if needed.
    7. Return an ``AuthenticatedPrincipal``.

    Raises ``AuthenticationError`` on failure.
    """
    email = _normalize_email(email)
    identity = await auth_repo.find_identity_by_email(db, email, identity_type)

    if identity is None:
        # Constant-time dummy verification to reduce timing differences
        hash_password("dummy-password-to-equalize-timing")
        raise AuthenticationError("Invalid email or password.")

    stored_hash = _get_password_hash(identity)
    if not verify_password(password, stored_hash):
        raise AuthenticationError("Invalid email or password.")

    # Account status checks
    if not identity.is_active:
        raise AccountDisabledError("This account has been deactivated.")

    # Rehash if hashing parameters have been upgraded
    if needs_password_rehash(stored_hash):
        new_hash = hash_password(password)
        await auth_repo.update_password_hash(
            db, identity.id, identity_type, new_hash
        )
        logger.info("Rehashed password for identity %s", identity.id)

    return _build_principal(identity, identity_type)


# ═════════════════════════════════════════════════════════════════════
# Session issuance
# ═════════════════════════════════════════════════════════════════════


async def issue_session(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IssuedSession:
    """
    Create a session record and issue access/refresh credentials.
    """
    now = datetime.now(tz.utc)
    session_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    raw_refresh = generate_refresh_token()
    refresh_hash = hash_refresh_token(raw_refresh)

    session, _ = await auth_repo.create_auth_session(
        db,
        identity_id=principal.identity_id,
        identity_type=principal.identity_type,
        refresh_hash=refresh_hash,
        session_expires_at=session_expires_at,
        token_expires_at=token_expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    access_token = create_access_token(
        subject=str(principal.identity_id),
        identity_type=principal.identity_type,
        session_id=str(session.id),
        organization_id=str(principal.organization_id),
        permissions=list(principal.permissions),
    )

    return IssuedSession(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ═════════════════════════════════════════════════════════════════════
# Token refresh
# ═════════════════════════════════════════════════════════════════════


async def refresh_session(
    db: AsyncSession,
    raw_refresh_token: str,
) -> IssuedSession:
    """
    Validate refresh-token record, detect replay, rotate atomically.

    1. Hash the presented token and locate its record (with row lock).
    2. Reject expired, revoked, or unknown tokens.
    3. If the token was already consumed → replay detected → revoke family.
    4. Atomically mark old consumed, create successor.
    5. Issue new access token.
    6. Return new credentials only after DB commit succeeds.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    lookup = await auth_repo.get_session_for_refresh(db, token_hash)

    if lookup is None:
        raise AuthenticationError("Invalid refresh token.")

    session, refresh_token = lookup

    # Check session-level revocation
    if not session.is_active:
        raise SessionExpiredError("Session has been revoked or expired.")

    # Replay detection: token was already consumed
    if refresh_token.consumed_at is not None:
        logger.warning(
            "Refresh token replay detected for session %s — revoking family.",
            session.id,
        )
        await auth_repo.revoke_session_family(db, session.id)
        raise TokenReplayError(
            "Refresh token has already been used. "
            "All sessions in this family have been revoked for security."
        )

    # Token-level checks
    if not refresh_token.is_usable:
        raise SessionExpiredError("Refresh token has expired or been revoked.")

    # Rotate: consume old, create successor
    now = datetime.now(tz.utc)
    new_raw_refresh = generate_refresh_token()
    new_hash = hash_refresh_token(new_raw_refresh)
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    await auth_repo.rotate_refresh_token(
        db,
        session_id=session.id,
        old_token_id=refresh_token.id,
        new_token_hash=new_hash,
        token_expires_at=new_expires_at,
    )

    # Reload identity to get current permissions and org_id
    identity = await auth_repo.find_identity_by_id(
        db, session.identity_id, session.identity_type
    )
    if identity is None or not identity.is_active:
        await auth_repo.revoke_session(db, session.id, reason="identity_removed")
        raise AuthenticationError("Identity no longer active.")

    principal = _build_principal(identity, session.identity_type, session.id)

    access_token = create_access_token(
        subject=str(principal.identity_id),
        identity_type=principal.identity_type,
        session_id=str(session.id),
        organization_id=str(principal.organization_id),
        permissions=list(principal.permissions),
    )

    return IssuedSession(
        access_token=access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ═════════════════════════════════════════════════════════════════════
# Logout
# ═════════════════════════════════════════════════════════════════════


async def logout_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """Revoke the caller's session."""
    await auth_repo.revoke_session(db, session_id, reason="logout")


async def logout_all_sessions(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
) -> int:
    """Revoke every session belonging to the authenticated identity."""
    return await auth_repo.revoke_all_sessions(
        db,
        principal.identity_id,
        principal.identity_type,
        reason="logout_all",
    )


# ═════════════════════════════════════════════════════════════════════
# Password management
# ═════════════════════════════════════════════════════════════════════


async def change_password(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
    current_password: str,
    new_password: str,
) -> None:
    """
    Verify current password, apply policy, update hash, revoke sessions.
    """
    identity = await auth_repo.find_identity_by_id(
        db, principal.identity_id, principal.identity_type
    )
    if identity is None:
        raise AuthenticationError("Identity not found.")

    stored_hash = _get_password_hash(identity)
    if not verify_password(current_password, stored_hash):
        raise AuthenticationError("Current password is incorrect.")

    validate_password_policy(new_password)
    new_hash = hash_password(new_password)

    await auth_repo.update_password_hash(
        db, principal.identity_id, principal.identity_type, new_hash
    )

    # Revoke all existing sessions — user must re-authenticate
    await auth_repo.revoke_all_sessions(
        db,
        principal.identity_id,
        principal.identity_type,
        reason="password_changed",
    )
    logger.info("Password changed for identity %s", principal.identity_id)


async def request_password_reset(email: str) -> None:
    """
    Initiate account recovery without disclosing account existence.

    In production this would generate a single-use token, store it,
    and send it via email.  The current implementation logs the
    request and returns immediately to avoid account enumeration.
    """
    email = _normalize_email(email)
    logger.info("Password reset requested for email: %s", email)
    # TODO: Generate reset token, store in DB, send email.
    # Intentionally returns nothing — generic 202 response.


async def reset_password(
    db: AsyncSession,
    reset_token: str,
    new_password: str,
) -> None:
    """
    Validate single-use reset token, update credentials, revoke sessions.

    Placeholder — requires the reset-token persistence and email
    infrastructure to be implemented first.
    """
    _ = db, reset_token, new_password
    # TODO: Look up reset token, validate expiry, update password, revoke sessions.
    raise NotImplementedError(
        "Password reset is not yet implemented. "
        "Requires email infrastructure and reset-token persistence."
    )


# ═════════════════════════════════════════════════════════════════════
# Principal resolution
# ═════════════════════════════════════════════════════════════════════


async def get_authenticated_principal(
    db: AsyncSession,
    subject: str,
    identity_type: str,
    session_id: str,
) -> AuthenticatedPrincipal:
    """
    Resolve identity from validated JWT claims and apply account-status
    checks.

    Called by the authentication dependency after JWT validation.
    """
    try:
        identity_id = uuid.UUID(subject)
        sid = uuid.UUID(session_id)
    except ValueError as exc:
        raise AuthenticationError("Malformed token claims.") from exc

    identity = await auth_repo.find_identity_by_id(db, identity_id, identity_type)
    if identity is None:
        raise AuthenticationError("Identity not found.")

    if not identity.is_active:
        raise AccountDisabledError("This account has been deactivated.")

    return _build_principal(identity, identity_type, sid)

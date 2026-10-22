"""
Database access layer for authentication sessions and refresh tokens.

All queries use parameterized ORM operations via the async SQLAlchemy
session.  This module never returns ORM objects directly to the API
layer — the service maps them to typed results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as tz

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Admin
from app.modules.auth.models import AuthSession, RefreshToken
from app.modules.organization.models import Organization


# ═════════════════════════════════════════════════════════════════════
# Identity lookup
# ═════════════════════════════════════════════════════════════════════


async def find_identity_by_email(
    db: AsyncSession,
    email: str,
    identity_type: str,
) -> Organization | Admin | None:
    """
    Find an organization or administrator account by normalized email.
    """
    if identity_type == "organization":
        stmt = select(Organization).where(
            Organization.organization_email == email
        )
    elif identity_type == "admin":
        stmt = select(Admin).where(Admin.admin_email == email)
    else:
        return None

    result = await db.execute(stmt)
    return result.scalars().first()


async def find_identity_by_id(
    db: AsyncSession,
    identity_id: uuid.UUID,
    identity_type: str,
) -> Organization | Admin | None:
    """Load an identity by trusted internal identifier."""
    if identity_type == "organization":
        stmt = select(Organization).where(Organization.id == identity_id)
    elif identity_type == "admin":
        stmt = select(Admin).where(Admin.id == identity_id)
    else:
        return None

    result = await db.execute(stmt)
    return result.scalars().first()


# ═════════════════════════════════════════════════════════════════════
# Session management
# ═════════════════════════════════════════════════════════════════════


async def create_auth_session(
    db: AsyncSession,
    *,
    identity_id: uuid.UUID,
    identity_type: str,
    refresh_hash: str,
    session_expires_at: datetime,
    token_expires_at: datetime,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[AuthSession, RefreshToken]:
    """
    Persist a new session and its initial refresh token atomically.
    """
    session = AuthSession(
        identity_id=identity_id,
        identity_type=identity_type,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=session_expires_at,
    )
    db.add(session)
    await db.flush()  # generate session.id

    token = RefreshToken(
        session_id=session.id,
        token_hash=refresh_hash,
        expires_at=token_expires_at,
    )
    db.add(token)
    await db.commit()
    await db.refresh(session)
    await db.refresh(token)
    return session, token


async def get_session_for_refresh(
    db: AsyncSession,
    token_hash: str,
) -> tuple[AuthSession, RefreshToken] | None:
    """
    Find the session and refresh-token record matching the given hash.

    Uses ``FOR UPDATE`` to prevent concurrent consumption of the
    same refresh token.
    """
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    result = await db.execute(stmt)
    refresh_token = result.scalars().first()

    if refresh_token is None:
        return None

    # Load the owning session
    session_stmt = select(AuthSession).where(
        AuthSession.id == refresh_token.session_id
    )
    session_result = await db.execute(session_stmt)
    session = session_result.scalars().first()

    if session is None:
        return None

    return session, refresh_token


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    old_token_id: uuid.UUID,
    new_token_hash: str,
    token_expires_at: datetime,
) -> RefreshToken:
    """
    Atomically consume the old refresh token and persist its successor.

    The old token is marked consumed and linked to the new token.
    """
    now = datetime.now(tz.utc)

    # Create successor
    new_token = RefreshToken(
        session_id=session_id,
        token_hash=new_token_hash,
        expires_at=token_expires_at,
    )
    db.add(new_token)
    await db.flush()  # generate new_token.id

    # Mark old token consumed and link successor
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.id == old_token_id)
        .values(consumed_at=now, replaced_by_id=new_token.id)
    )
    await db.execute(stmt)
    await db.commit()
    await db.refresh(new_token)
    return new_token


# ═════════════════════════════════════════════════════════════════════
# Session revocation
# ═════════════════════════════════════════════════════════════════════


async def revoke_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    reason: str = "logout",
) -> bool:
    """Revoke a single session and all its refresh tokens."""
    now = datetime.now(tz.utc)

    # Revoke the session
    stmt = (
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason=reason)
    )
    result = await db.execute(stmt)

    # Revoke all tokens belonging to this session
    token_stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.session_id == session_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.execute(token_stmt)
    await db.commit()

    return result.rowcount > 0


async def revoke_all_sessions(
    db: AsyncSession,
    identity_id: uuid.UUID,
    identity_type: str,
    reason: str = "logout_all",
) -> int:
    """Revoke every session for an identity.  Returns count revoked."""
    now = datetime.now(tz.utc)

    # Find all active sessions for this identity
    session_stmt = select(AuthSession.id).where(
        AuthSession.identity_id == identity_id,
        AuthSession.identity_type == identity_type,
        AuthSession.revoked_at.is_(None),
    )
    result = await db.execute(session_stmt)
    session_ids = [row[0] for row in result.all()]

    if not session_ids:
        return 0

    # Revoke sessions
    revoke_sessions_stmt = (
        update(AuthSession)
        .where(AuthSession.id.in_(session_ids))
        .values(revoked_at=now, revocation_reason=reason)
    )
    await db.execute(revoke_sessions_stmt)

    # Revoke all tokens in those sessions
    revoke_tokens_stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.session_id.in_(session_ids),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.execute(revoke_tokens_stmt)
    await db.commit()

    return len(session_ids)


async def revoke_session_family(
    db: AsyncSession,
    session_id: uuid.UUID,
    reason: str = "refresh_token_replay",
) -> None:
    """
    Revoke the entire session including all tokens — used when
    refresh-token replay is detected.
    """
    await revoke_session(db, session_id, reason)


# ═════════════════════════════════════════════════════════════════════
# Password update
# ═════════════════════════════════════════════════════════════════════


async def update_password_hash(
    db: AsyncSession,
    identity_id: uuid.UUID,
    identity_type: str,
    new_hash: str,
) -> bool:
    """Persist a new password hash for the given identity."""
    if identity_type == "organization":
        stmt = (
            update(Organization)
            .where(Organization.id == identity_id)
            .values(organization_hashed_password=new_hash)
        )
    elif identity_type == "admin":
        stmt = (
            update(Admin)
            .where(Admin.id == identity_id)
            .values(admin_hashed_password=new_hash)
        )
    else:
        return False

    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

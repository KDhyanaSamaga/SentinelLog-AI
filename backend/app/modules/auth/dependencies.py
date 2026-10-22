"""
FastAPI authentication dependencies.

These dependencies establish a trusted identity for every protected
endpoint.  They extract bearer credentials, validate the access JWT,
and resolve the identity from the database.
"""

from __future__ import annotations

from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.auth.service import (
    AccountDisabledError,
    AuthenticationError,
    get_authenticated_principal,
)
from app.modules.auth.types import AuthenticatedPrincipal

_bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ═════════════════════════════════════════════════════════════════════
# Core dependency
# ═════════════════════════════════════════════════════════════════════


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedPrincipal:
    """
    Extract bearer token, validate the access JWT, and resolve the
    identity from the database.

    Raises ``401`` on any validation or resolution failure.
    """
    token = credentials.credentials

    # Decode and validate JWT
    try:
        claims = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise _CREDENTIALS_EXCEPTION

    # Resolve identity from DB (checks is_active, etc.)
    try:
        principal = await get_authenticated_principal(
            db,
            subject=claims.sub,
            identity_type=claims.type,
            session_id=claims.sid,
        )
    except AccountDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated.",
        )
    except AuthenticationError:
        raise _CREDENTIALS_EXCEPTION

    return principal


# ═════════════════════════════════════════════════════════════════════
# Identity-type guards
# ═════════════════════════════════════════════════════════════════════


async def get_current_organization(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """Require that the caller is an organization identity."""
    if principal.identity_type != "organization":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires an organization identity.",
        )
    return principal


async def get_current_admin(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """Require that the caller is an admin identity."""
    if principal.identity_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires an admin identity.",
        )
    return principal


# ═════════════════════════════════════════════════════════════════════
# Permission guard
# ═════════════════════════════════════════════════════════════════════


def require_permission(permission: str) -> Callable:
    """
    Build a FastAPI dependency that verifies a named permission.

    Usage::

        @router.get("/incidents", dependencies=[Depends(require_permission("incidents:read"))])
        async def list_incidents(...):
            ...
    """

    async def _check(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if permission not in principal.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return principal

    return _check


# ═════════════════════════════════════════════════════════════════════
# Account-status guard
# ═════════════════════════════════════════════════════════════════════


async def require_active_identity(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """
    Enforce that the identity is still active.

    This is already checked in ``get_authenticated_principal``, but
    this dependency provides an explicit, documentable guard for
    routes that need it.
    """
    # Account-status is verified during principal resolution.
    # This dependency exists for explicitness and composability.
    return principal

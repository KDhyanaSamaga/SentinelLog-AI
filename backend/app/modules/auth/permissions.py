"""
Authorization policies and tenant-isolation enforcement.

Three layers:
  1. **Identity type** — organization vs admin
  2. **Permission** — named action grants (``incidents:read``, etc.)
  3. **Tenant ownership** — resource belongs to the caller's organization

These functions raise ``HTTPException(403)`` on failure.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.modules.auth.types import AuthenticatedPrincipal


def ensure_organization_owns_resource(
    principal: AuthenticatedPrincipal,
    resource_organization_id: uuid.UUID,
) -> None:
    """
    Verify that the requested resource belongs to the caller's
    organization.

    Raises ``403 Forbidden`` when the ownership check fails.
    """
    if principal.organization_id != resource_organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )


def ensure_identity_type(
    principal: AuthenticatedPrincipal,
    required_type: str,
) -> None:
    """
    Verify that the caller's identity type matches the requirement.

    Raises ``403 Forbidden`` on mismatch.
    """
    if principal.identity_type != required_type:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires a {required_type} identity.",
        )


def ensure_has_permission(
    principal: AuthenticatedPrincipal,
    permission: str,
) -> None:
    """
    Verify that the caller holds the named permission.

    Raises ``403 Forbidden`` when the permission is missing.
    """
    if permission not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {permission}",
        )


def ensure_self_or_admin(
    principal: AuthenticatedPrincipal,
    target_identity_id: uuid.UUID,
) -> None:
    """
    Allow the action only if the caller is acting on their own
    identity or is a platform administrator.

    Raises ``403 Forbidden`` otherwise.
    """
    if principal.identity_id != target_identity_id:
        # In the future, check for ``platform:admin`` permission here
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only perform this action on your own account.",
        )

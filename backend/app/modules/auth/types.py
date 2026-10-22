"""
Internal domain types shared across the auth module.

These are not request/response schemas — they are typed containers
for service-layer results and authenticated identity information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """
    A fully validated, trusted identity resolved from credentials.

    ``organization_id`` is always present:
    - For organization identities: their own UUID.
    - For admin identities: the UUID of the organization they belong to.
    """

    identity_id: UUID
    identity_type: str  # "organization" | "admin"
    organization_id: UUID
    permissions: frozenset[str] = field(default_factory=frozenset)
    session_id: UUID | None = None


@dataclass(frozen=True)
class IssuedSession:
    """Credentials returned after successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0  # seconds until access-token expiry


# ── Default permission sets ──────────────────────────────────────────

ORGANIZATION_DEFAULT_PERMISSIONS: frozenset[str] = frozenset({
    "organization:read",
    "organization:manage",
    "incidents:read",
    "incidents:write",
    "logs:read",
    "logs:write",
    "users:manage",
})

ADMIN_DEFAULT_PERMISSIONS: frozenset[str] = frozenset({
    "organization:read",
    "incidents:read",
    "incidents:write",
    "logs:read",
    "logs:write",
})

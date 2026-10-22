"""
Cryptographic primitives and token encoding/decoding.

This module owns password hashing (Argon2id), JWT creation/validation,
and refresh-token generation.  No other module should directly call
hashing libraries or construct tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import argon2
import jwt
from pydantic import BaseModel, field_validator

from app.core.config import settings

# ── Argon2id password hasher ──────────────────────────────────────────

_password_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID,
)


# ── Commonly compromised passwords (minimal blocklist) ────────────────

_COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "iloveyou", "admin123", "letmein12", "welcome1",
    "monkey123", "dragon12", "master12", "qwerty12", "login123",
    "abc12345", "password123", "admin1234", "root1234", "changeme",
})


# ── Typed JWT claims ─────────────────────────────────────────────────

class AccessTokenClaims(BaseModel):
    """Validated JWT access-token claims."""

    sub: str            # identity UUID as string
    type: str           # "organization" or "admin"
    sid: str            # session UUID as string
    org: str | None = None  # organization UUID (own id for orgs, org FK for admins)
    perms: list[str] = []   # granted permissions
    iss: str
    aud: str
    iat: int
    exp: int
    jti: str

    @field_validator("type")
    @classmethod
    def _validate_identity_type(cls, v: str) -> str:
        if v not in ("organization", "admin"):
            raise ValueError(f"Invalid identity type: {v!r}")
        return v



# Password functions
def validate_password_policy(password: str) -> None:
    """
    Enforce the configured password policy.

    Raises ``ValueError`` on policy violation.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
        )
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must not exceed {settings.PASSWORD_MAX_LENGTH} characters."
        )
    if password.lower() in _COMMON_PASSWORDS:
        raise ValueError(
            "This password is too common. Please choose a stronger password."
        )


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a password against a stored Argon2id hash."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except argon2.exceptions.VerifyMismatchError:
        return False
    except argon2.exceptions.InvalidHashError:
        return False


def needs_password_rehash(password_hash: str) -> bool:
    """Check whether the stored hash parameters need upgrading."""
    return _password_hasher.check_needs_rehash(password_hash)


# JWT functions
def create_access_token(
    subject: str,
    identity_type: str,
    session_id: str,
    organization_id: str | None = None,
    permissions: list[str] | None = None,
) -> str:
    """
    Create a signed JWT access token with controlled claims and expiry.

    Parameters
    ----------
    subject : str
        Identity UUID as a string.
    identity_type : str
        ``"organization"`` or ``"admin"``.
    session_id : str
        Session UUID as a string.
    organization_id : str | None
        Organization UUID for tenant scoping.
    permissions : list[str] | None
        Granted permission strings.

    Returns
    -------
    str
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": identity_type,
        "sid": session_id,
        "org": organization_id,
        "perms": permissions or [],
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> AccessTokenClaims:
    """
    Verify signature, algorithm, issuer, audience, expiry and required
    claims of a JWT access token.

    Raises ``jwt.InvalidTokenError`` (or a subclass) on any validation
    failure.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={
            "require": ["sub", "type", "sid", "iss", "aud", "iat", "exp", "jti"],
        },
    )

    return AccessTokenClaims(**payload)



# Refresh-token functions
def generate_refresh_token() -> str:
    """Generate a cryptographically random opaque refresh credential."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """
    Hash the refresh token for database storage and lookup.

    Uses SHA-256 — appropriate for high-entropy random tokens where
    offline brute-force is not a practical concern.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()



# Utility
def constant_time_secret_match(candidate: str, expected: str) -> bool:
    """Compare two secret-derived string values in constant time."""
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
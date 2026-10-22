"""
Request validation and safe response serialization schemas for
the authentication module.

Rules:
- Reject oversized input before expensive processing.
- Never place passwords or tokens in response schemas.
- Use generic responses for account-recovery to prevent enumeration.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ═════════════════════════════════════════════════════════════════════
# Helper
# ═════════════════════════════════════════════════════════════════════

def _normalize_email(email: str) -> str:
    """Lowercase and strip whitespace — no provider-specific rules."""
    return email.strip().lower()


# ═════════════════════════════════════════════════════════════════════
# Request schemas
# ═════════════════════════════════════════════════════════════════════


class RegisterOrganizationRequest(BaseModel):
    """Validate organization registration input."""

    organization_name: str = Field(min_length=2, max_length=255)
    organization_email: EmailStr
    organization_phone: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("organization_email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return _normalize_email(v)


class LoginRequest(BaseModel):
    """
    Authenticate an identity.

    ``identity_type`` selects whether the email is looked up in the
    organization or admin table.  Defaults to ``"organization"``.
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    identity_type: str = "organization"

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("identity_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in ("organization", "admin"):
            raise ValueError("identity_type must be 'organization' or 'admin'")
        return v


class RefreshRequest(BaseModel):
    """Renew authentication using an opaque refresh token."""

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    """
    End the current session.

    ``session_id`` is optional — when omitted the server revokes the
    session derived from the caller's access token.
    """

    session_id: UUID | None = None


class ChangePasswordRequest(BaseModel):
    """Change credentials — requires re-verification."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match.")
        return self


class ForgotPasswordRequest(BaseModel):
    """Start generic account-recovery flow."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    """Complete account recovery with a single-use reset token."""

    reset_token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


# ═════════════════════════════════════════════════════════════════════
# Response schemas
# ═════════════════════════════════════════════════════════════════════


class TokenResponse(BaseModel):
    """Return authentication credentials (never include password data)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access-token expiry


class CurrentPrincipalResponse(BaseModel):
    """Return the current authenticated identity's safe profile."""

    identity_id: UUID
    identity_type: str
    organization_id: UUID
    permissions: list[str]


class MessageResponse(BaseModel):
    """Generic message envelope for non-data responses."""

    message: str
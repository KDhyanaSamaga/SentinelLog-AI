"""
Authentication session and refresh-token persistence models.

``AuthSession`` tracks login sessions for both Organization and Admin
identities using a polymorphic ``identity_type`` discriminator.

``RefreshToken`` tracks the refresh-token chain within a session,
enabling replay detection by recording consumed and successor tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as tz

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AuthSession(Base):
    """Represents an authenticated login session."""

    __tablename__ = "auth_session"
    __table_args__ = (
        CheckConstraint(
            "identity_type IN ('organization', 'admin')",
            name="ck_auth_session_identity_type",
        ),
        Index("ix_auth_session_identity", "identity_id", "identity_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Polymorphic owner reference ───────────────────────────
    # Not a foreign key — can reference either organization.id or admin.id.
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    identity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # ── Request metadata ──────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revocation_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RefreshToken.created_at",
    )

    @property
    def is_active(self) -> bool:
        """Session is active if not revoked and not expired."""
        now = datetime.now(tz.utc)
        return self.revoked_at is None and self.expires_at > now


class RefreshToken(Base):
    """Represents a single refresh token in a rotation chain."""

    __tablename__ = "refresh_token"
    __table_args__ = (
        Index("ix_refresh_token_token_hash", "token_hash", unique=True),
        Index("ix_refresh_token_session_id", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_session.id", ondelete="CASCADE"),
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex digest = 64 chars
        nullable=False,
        unique=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Successor token record (for replay detection chain).
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_token.id"),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────
    session: Mapped["AuthSession"] = relationship(
        back_populates="refresh_tokens",
    )

    @property
    def is_usable(self) -> bool:
        """Token is usable if not consumed, not revoked, and not expired."""
        now = datetime.now(tz.utc)
        return (
            self.consumed_at is None
            and self.revoked_at is None
            and self.expires_at > now
        )

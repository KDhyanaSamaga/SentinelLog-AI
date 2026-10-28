"""create authentication sessions and refresh tokens

Revision ID: 9a1f2c3d4e5f
Revises: 653434db7efd
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a1f2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "653434db7efd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("identity_id", sa.UUID(), nullable=False),
        sa.Column("identity_type", sa.String(length=20), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "identity_type IN ('organization', 'admin')",
            name="ck_auth_session_identity_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_session_identity",
        "auth_session",
        ["identity_id", "identity_type"],
    )
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["auth_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["refresh_token.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_refresh_token_token_hash",
        "refresh_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_token_session_id",
        "refresh_token",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_session_id", table_name="refresh_token")
    op.drop_index("ix_refresh_token_token_hash", table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_index("ix_auth_session_identity", table_name="auth_session")
    op.drop_table("auth_session")

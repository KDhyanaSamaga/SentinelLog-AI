"""add organization ownership to log tables

Revision ID: b7c8d9e0f1a2
Revises: 9a1f2c3d4e5f
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "9a1f2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "log_records",
        sa.Column("organization_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_log_records_organization_id",
        "log_records",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_log_records_organization_id",
        "log_records",
        ["organization_id"],
    )
    op.add_column(
        "log_explainability",
        sa.Column("organization_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "log_explainability",
        sa.Column(
            "attack_type",
            sa.String(length=255),
            nullable=False,
            server_default="Unknown",
        ),
    )
    op.add_column(
        "log_explainability",
        sa.Column(
            "mitre_attack_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.create_foreign_key(
        "fk_log_explainability_organization_id",
        "log_explainability",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_log_explainability_organization_id",
        "log_explainability",
        ["organization_id"],
    )

    bind = op.get_bind()
    organization_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM organization")
    ).scalar_one()
    if organization_count != 1:
        raise RuntimeError(
            "Tenant migration found legacy logs but cannot infer their owner. "
            "Create exactly one organization or backfill organization_id "
            "before rerunning this migration."
        )
    organization_id = bind.execute(
        sa.text("SELECT id FROM organization ORDER BY created_at LIMIT 1")
    ).scalar_one()
    bind.execute(
        sa.text(
            "UPDATE log_records SET organization_id = :organization_id "
            "WHERE organization_id IS NULL"
        ),
        {"organization_id": organization_id},
    )
    bind.execute(
        sa.text(
            "UPDATE log_explainability SET organization_id = :organization_id "
            "WHERE organization_id IS NULL"
        ),
        {"organization_id": organization_id},
    )
    legacy_count = bind.execute(
        sa.text(
            "SELECT (SELECT COUNT(*) FROM log_records WHERE organization_id IS NULL) "
            "+ (SELECT COUNT(*) FROM log_explainability WHERE organization_id IS NULL)"
        )
    ).scalar_one()
    if legacy_count:
        raise RuntimeError(
            "Tenant migration found existing unowned log rows. "
            "Backfill organization_id for log_records and log_explainability, "
            "then rerun this migration."
        )

    op.alter_column(
        "log_records",
        "organization_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "log_explainability",
        "organization_id",
        existing_type=sa.UUID(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_log_explainability_organization_id",
        table_name="log_explainability",
    )
    op.drop_constraint(
        "fk_log_explainability_organization_id",
        "log_explainability",
        type_="foreignkey",
    )
    op.drop_column("log_explainability", "organization_id")
    op.drop_column("log_explainability", "mitre_attack_ids")
    op.drop_column("log_explainability", "attack_type")
    op.drop_index("ix_log_records_organization_id", table_name="log_records")
    op.drop_constraint(
        "fk_log_records_organization_id",
        "log_records",
        type_="foreignkey",
    )
    op.drop_column("log_records", "organization_id")

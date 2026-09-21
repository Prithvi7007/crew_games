"""CREW v13 account roles and managed settings.

Revision ID: v13_access
Revises: v12_platform
"""
from alembic import op
import sqlalchemy as sa

revision = "v13_access"
down_revision = "v12_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("role", sa.Text(), nullable=False, server_default="player"),
    )
    op.create_index("ix_profiles_role", "profiles", ["role"])

    op.create_table(
        "system_settings",
        sa.Column("setting_key", sa.Text(), primary_key=True),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index("ix_profiles_role", table_name="profiles")
    op.drop_column("profiles", "role")

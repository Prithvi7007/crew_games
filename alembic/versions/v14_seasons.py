"""CREW v14 season foundation.

Revision ID: v14_seasons
Revises: v13_access
"""
from alembic import op
import sqlalchemy as sa

revision = "v14_seasons"
down_revision = "v13_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Text(), nullable=False),
        sa.Column("end_date", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("season_number", name="uq_seasons_number"),
        sa.UniqueConstraint("slug", name="uq_seasons_slug"),
        sa.CheckConstraint("start_date <= end_date", name="ck_seasons_date_order"),
    )
    op.create_index("ix_seasons_date_range", "seasons", ["start_date", "end_date"])

    op.execute(
        """
        INSERT INTO seasons (season_number, slug, name, start_date, end_date)
        VALUES (1, 'season-1', 'Launch Season', '2026-09-21', '2026-10-30')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_seasons_date_range", table_name="seasons")
    op.drop_table("seasons")

"""One-time CREW Trophy Room launch tour completion tracking.

Revision ID: v16_trophy_tour
Revises: v15_badges
"""
from alembic import op
import sqlalchemy as sa

revision = "v16_trophy_tour"
down_revision = "v15_badges"
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "trophy_tour_completions",
        sa.Column("profile_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tour_key", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=False),
        sa.Column("completion_type", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "tour_key", name="pk_trophy_tour_completions"),
        sa.CheckConstraint("completion_type IN ('finished','skipped')", name="ck_trophy_tour_completion_type"),
    )


def downgrade() -> None:
    op.drop_table("trophy_tour_completions")

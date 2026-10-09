"""Season-specific badge awards and immutable championship snapshot storage.

Revision ID: v15_badges
Revises: v14_seasons
"""

from alembic import op
import sqlalchemy as sa

revision = "v15_badges"
down_revision = "v14_seasons"
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "badge_awards",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("profile_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("badge_code", sa.Text(), nullable=False),
        sa.Column("awarded_at", sa.Text(), nullable=False),
        sa.Column("source_date", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("profile_id", "season_id", "badge_code", name="uq_badge_awards_player_season_code"),
        sa.CheckConstraint("length(badge_code) > 0", name="ck_badge_awards_nonempty_code"),
    )
    op.create_index("ix_badge_awards_season_code", "badge_awards", ["season_id", "badge_code"])
    op.create_index("ix_badge_awards_profile_season", "badge_awards", ["profile_id", "season_id"])

    op.create_table(
        "badge_showcase",
        sa.Column("profile_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("badge_award_id", ID, sa.ForeignKey("badge_awards.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "slot", name="pk_badge_showcase"),
        sa.UniqueConstraint("badge_award_id", name="uq_badge_showcase_award"),
        sa.CheckConstraint("slot BETWEEN 1 AND 3", name="ck_badge_showcase_slot"),
    )

    op.create_table(
        "season_badge_finalizations",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("finalized_at", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.CheckConstraint("rule_version > 0", name="ck_season_badge_finalizations_rule_version"),
    )


def downgrade() -> None:
    op.drop_table("season_badge_finalizations")
    op.drop_table("badge_showcase")
    op.drop_index("ix_badge_awards_profile_season", table_name="badge_awards")
    op.drop_index("ix_badge_awards_season_code", table_name="badge_awards")
    op.drop_table("badge_awards")

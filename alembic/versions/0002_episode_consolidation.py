"""Ajoute consolidated/consolidated_key à memory_episodes (consolidation épisodique → sémantique).

Revision ID: 0002_episode_consolidation
Revises: 0001_initial
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_episode_consolidation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_episodes",
        sa.Column("consolidated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "memory_episodes",
        sa.Column("consolidated_key", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memory_episodes", "consolidated_key")
    op.drop_column("memory_episodes", "consolidated")

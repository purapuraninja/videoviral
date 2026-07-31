"""M4: no VPS video storage — preview resolution fields.

Adds ``agent_id`` to ``video_outputs`` (the render PC holding a binary artifact)
and ``preview_base_url`` to ``agents`` (the PC's Tailscale preview server), so
the VPS can proxy a live stream instead of storing files.

Fresh installs get these columns from 0001's ``create_all``; this migration is a
no-op-safe ALTER for existing databases.

Revision ID: 0002_no_vps_storage
Revises: 0001_initial
Create Date: 2026-07-31 00:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import Column, String, inspect

revision: str = "0002_no_vps_storage"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "agent_id" not in _columns("video_outputs"):
        op.add_column("video_outputs", Column("agent_id", String, nullable=True))
    if "preview_base_url" not in _columns("agents"):
        op.add_column(
            "agents",
            Column("preview_base_url", String(255), nullable=False, server_default=""),
        )


def downgrade() -> None:
    if "preview_base_url" in _columns("agents"):
        op.drop_column("agents", "preview_base_url")
    if "agent_id" in _columns("video_outputs"):
        op.drop_column("video_outputs", "agent_id")

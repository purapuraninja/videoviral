"""M6: publishing — publish_targets table + publish render-job statuses.

Adds the ``publish_targets`` table and widens the ``render_job_status_valid``
CheckConstraint to allow ``publishing``, ``published`` and ``publish_failed``.

Fresh installs get everything from 0001's ``create_all``; this migration is
idempotent for existing databases.

Revision ID: 0003_publishing
Revises: 0002_no_vps_storage
Create Date: 2026-07-31 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_publishing"
down_revision: Union[str, None] = "0002_no_vps_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = (
    "'queued','claimed','scripting','assets','tts','subtitles',"
    "'rendering','uploading','completed','failed','cancelled','retry_waiting'"
)
_NEW_STATUSES = (
    "'queued','claimed','scripting','assets','tts','subtitles',"
    "'rendering','uploading','completed','publishing','published',"
    "'failed','cancelled','retry_waiting','publish_failed'"
)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("publish_targets"):
        op.create_table(
            "publish_targets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "job_id",
                sa.String(),
                sa.ForeignKey("render_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("platform", sa.String(32), nullable=False),
            sa.Column("mode", sa.String(16), nullable=False, server_default="auto"),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("post_url", sa.Text(), nullable=True),
            sa.Column("platform_post_id", sa.String(128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("request_json", sa.JSON(), nullable=True),
            sa.Column("claimed_by_agent_id", sa.String(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "status in ('pending','publishing','published','failed',"
                "'manual_required','skipped')",
                name="publish_target_status_valid",
            ),
            sa.CheckConstraint("mode in ('auto','manual')", name="publish_target_mode_valid"),
            sa.UniqueConstraint("job_id", "platform", name="uq_publish_target_job_platform"),
        )
        op.create_index("ix_publish_targets_status", "publish_targets", ["status"])

    # Widen the render job status constraint to include the publishing states.
    op.drop_constraint("render_job_status_valid", "render_jobs", type_="check")
    op.create_check_constraint(
        "render_job_status_valid", "render_jobs", f"status in ({_NEW_STATUSES})"
    )


def downgrade() -> None:
    # Publishing states must be cleared before narrowing the constraint.
    op.execute(
        "update render_jobs set status='completed' "
        "where status in ('publishing','published','publish_failed')"
    )
    op.drop_constraint("render_job_status_valid", "render_jobs", type_="check")
    op.create_check_constraint(
        "render_job_status_valid", "render_jobs", f"status in ({_OLD_STATUSES})"
    )
    if _has_table("publish_targets"):
        op.drop_index("ix_publish_targets_status", table_name="publish_targets")
        op.drop_table("publish_targets")

"""Initial schema: all VVF tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-29 00:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy.engine import Connection

from vvf_database.base import Base
from vvf_database import models  # noqa: F401  (register all mappers/metadata)

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _bind() -> Connection:
    return op.get_bind()


def upgrade() -> None:
    # Create every table defined on Base.metadata in dependency order.
    Base.metadata.create_all(_bind())


def downgrade() -> None:
    # Drop in reverse dependency order.
    Base.metadata.drop_all(_bind())

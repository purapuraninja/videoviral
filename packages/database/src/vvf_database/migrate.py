"""Thin CLI wrapper around Alembic so services can run migrations easily.

Usage::

    python -m vvf_database.migrate upgrade head
    python -m vvf_database.migrate downgrade -1
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic import command

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent  # packages/database
ALEMBIC_INI = PKG_ROOT / "alembic.ini"
MIGRATIONS_DIR = PKG_ROOT / "alembic"


def build_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m vvf_database.migrate <upgrade|downgrade> [revision]")
        return 2
    cfg = build_config()
    cmd = argv[0]
    rev = argv[1] if len(argv) > 1 else "head"
    if cmd == "upgrade":
        command.upgrade(cfg, rev)
    elif cmd == "downgrade":
        command.downgrade(cfg, rev)
    elif cmd == "current":
        command.current(cfg)
    elif cmd == "heads":
        command.heads(cfg)
    elif cmd == "history":
        command.history(cfg)
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

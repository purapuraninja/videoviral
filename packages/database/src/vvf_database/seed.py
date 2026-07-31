"""Seed default admin user and default render profiles.

Run with: ``python -m vvf_database.seed``
"""

from __future__ import annotations

import os
import sys

from passlib.context import CryptContext

from vvf_database.base import Base
from vvf_database.models import RenderProfile, User
from vvf_database.session import build_engine, get_session_factory
from vvf_shared.security import PwdContext

DEFAULT_PROFILES = [
    {
        "name": "TikTok ID 45s",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "duration_seconds": 45,
        "language": "id-ID",
        "platforms": ["tiktok", "youtube_shorts", "instagram_reels"],
        "voice_config": {"provider": "edge", "voice": "id-ID-ArdiNeural"},
        "subtitle_config": {"style": "bold-center", "position": "bottom"},
        "music_config": {"profile": "news-modern"},
    },
    {
        "name": "Shorts ID 30s",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "duration_seconds": 30,
        "language": "id-ID",
        "platforms": ["youtube_shorts"],
        "voice_config": {"provider": "edge", "voice": "id-ID-GadisNeural"},
        "subtitle_config": {"style": "bold-center", "position": "bottom"},
        "music_config": {"profile": "upbeat"},
    },
]


def seed() -> None:
    engine = build_engine()
    Base.metadata.create_all(engine)  # idempotent; real schema lives in Alembic
    factory = get_session_factory(engine)
    with factory() as session:
        username = os.getenv("VVF_ADMIN_USERNAME", "admin")
        password = os.getenv("VVF_ADMIN_PASSWORD", "changeme")
        existing = session.query(User).filter_by(username=username).first()
        if existing is None:
            session.add(
                User(username=username, password_hash=PwdContext.hash(password), is_admin=True)
            )
            print(f"[seed] created admin user '{username}'")
        else:
            existing.password_hash = PwdContext.hash(password)
            print(f"[seed] reset password for existing user '{username}'")

        for profile in DEFAULT_PROFILES:
            exists = session.query(RenderProfile).filter_by(name=profile["name"]).first()
            if exists is None:
                session.add(RenderProfile(**profile))
                print(f"[seed] created render profile '{profile['name']}'")

        session.commit()
    print("[seed] done")


if __name__ == "__main__":
    sys.exit(seed())

"""VVF database package: SQLAlchemy models, session, migrations, and seed."""

from vvf_database.base import Base
from vvf_database.models import (
    Agent,
    Approval,
    CandidateSource,
    ContentCandidate,
    RenderJob,
    RenderJobEvent,
    RenderProfile,
    ResearchQuery,
    ResearchRun,
    SourceDocument,
    User,
    VideoOutput,
)
from vvf_database.session import (
    build_engine,
    get_session,
    get_session_factory,
    make_dsn,
)

__all__ = [
    "Base",
    "build_engine",
    "get_session",
    "get_session_factory",
    "make_dsn",
    # models
    "Agent",
    "Approval",
    "CandidateSource",
    "ContentCandidate",
    "RenderJob",
    "RenderJobEvent",
    "RenderProfile",
    "ResearchQuery",
    "ResearchRun",
    "SourceDocument",
    "User",
    "VideoOutput",
]

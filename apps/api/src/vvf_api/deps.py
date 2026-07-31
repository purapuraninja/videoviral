"""FastAPI dependencies: DB session, current admin user, agent auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from vvf_database.session import build_engine, get_session_factory
from vvf_shared.config import get_settings
from vvf_shared.security import PwdContext

_engine = None
_session_factory = None


def get_db() -> Session:
    """Yield a DB session. Lazily builds a shared engine/factory."""
    global _engine, _session_factory
    if _engine is None:
        _engine = build_engine()
        _session_factory = get_session_factory(_engine)
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_admin(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    vvf_session: Annotated[str | None, Cookie()] = None,
) -> str:
    """Validate a session cookie/bearer and return the admin's user id.

    Accepts either an ``Authorization: Bearer <token>`` header (used by the
    local render agent and curl) or the ``vvf_session`` cookie set at login
    (used by the browser dashboard, sent automatically with credentials).
    Returns the user's primary-key id so FK columns like created_by stay valid.
    """
    from vvf_api.auth import session_verifier
    from vvf_database.models import User

    raw = authorization
    if (raw is None or not raw.startswith("Bearer ")) and vvf_session:
        raw = vvf_session
    username = session_verifier(raw)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.query(User).filter_by(username=username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin user not found"
        )
    return user.id


CurrentAdmin = Annotated[str, Depends(get_current_admin)]


def verify_admin_credentials(username: str, password: str) -> str | None:
    """Used by the login endpoint to check the single admin user."""
    settings = get_settings()
    if username == settings.admin_username and password == settings.admin_password:
        return username
    return None


def verify_password(plain: str, hashed: str) -> bool:
    return PwdContext.verify(plain, hashed)

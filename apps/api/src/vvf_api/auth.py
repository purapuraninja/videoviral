"""Single-admin authentication via signed session cookies.

MVP scope (IMPLEMENTATION_PLAN.md §12): single-admin credentials plus secure
session cookies. Uses ``itsdangerous`` to sign a compact session token returned
as a cookie and accepted as a Bearer header.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from vvf_api.deps import CurrentAdmin, DbSession, verify_admin_credentials
from vvf_shared.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_SESSION_TTL_SECONDS = 60 * 60 * 12  # 12 hours


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    username: str
    session_token: str


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="vvf-session")


def issue_session(username: str) -> str:
    return _serializer().dumps({"u": username})


def session_verifier(authorization: str | None) -> str | None:
    """Return the username encoded in a bearer session token, or None."""
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=_SESSION_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("u")


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, response: Response) -> LoginOut:
    username = verify_admin_credentials(body.username, body.password)
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = issue_session(username)
    response.set_cookie(
        key="vvf_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().env == "production",
        max_age=_SESSION_TTL_SECONDS,
    )
    return LoginOut(username=username, session_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie("vvf_session")


@router.get("/me")
def me(username: CurrentAdmin) -> dict:
    from datetime import datetime, timezone

    return {
        "service": "vvf-api",
        "username": username,
        "time": datetime.now(timezone.utc).isoformat(),
    }

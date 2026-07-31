"""Security helpers: password hashing, API token generation, idempotency keys."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt


class PwdContext:
    """Password hashing context using bcrypt directly (avoids passlib bugs)."""

    @staticmethod
    def hash(password: str) -> str:
        pw = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8")[:72], password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False


def hash_token(token: str) -> str:
    """Hash an API token for at-rest storage (SHA-256)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenManager:
    """Generate and verify opaque bearer tokens for local render agents.

    Tokens are returned to the agent exactly once and stored only as a hash.
    """

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def issue(self, agent_id: str) -> str:
        raw = f"{agent_id}.{secrets.token_urlsafe(32)}"
        return raw

    @staticmethod
    def fingerprint(token: str) -> str:
        """Storable fingerprint of a token (used to look up agents)."""
        return hash_token(token)

    def _sign(self, token: str) -> str:
        return hmac.new(self._secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def generate_idempotency_key() -> str:
    """Random idempotency key so a network retry cannot create duplicate renders."""
    return secrets.token_urlsafe(24)


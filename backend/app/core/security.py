"""
JWT token creation/validation and password hashing utilities.

- Access tokens: short-lived (default 15 min), contain user ID + role + scopes
- Refresh tokens: longer-lived (default 7 days), contain user ID only
- Passwords: bcrypt via passlib (cost factor 12)

JWT secret is loaded through SecretsProvider (FR-004, Constitution P9).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import get_settings

# ---------------------------------------------------------------------------
# Password hashing context
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* value."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Token payload schema
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """Decoded JWT payload — validated on every authenticated request."""
    sub: str                    # user ID (UUID string)
    role: str = ""              # user role (empty string for refresh tokens)
    scopes: list[str] = []      # role-specific scopes (FR-003a)
    exp: int | None = None      # unix timestamp (jose returns int, not datetime)
    jti: str | None = None      # JWT ID (for refresh token rotation)
    type: str = "access"        # "access" | "refresh"


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def _build_scopes(role: str) -> list[str]:
    """
    Return the scope list for *role* per FR-003a.

    Intake  → case:create, case:read, document:upload, policy:read
    Nurse   → case:read, case:lock, case:decide, history:read
    Admin   → case:*, policy:*, user:manage, audit:read, history:read
    """
    _ROLE_SCOPES: dict[str, list[str]] = {
        "intake": ["case:create", "case:read", "document:upload", "policy:read"],
        "nurse": ["case:read", "case:lock", "case:decide", "history:read"],
        "admin": ["case:*", "policy:*", "user:manage", "audit:read", "history:read"],
    }
    return _ROLE_SCOPES.get(role, [])


def create_access_token(
    subject: str,
    role: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    subject
        User ID (UUID string).
    role
        User's role string — used to derive scopes.
    extra_claims
        Any additional claims to embed.
    expires_delta
        Override the default expiry from settings.
    """
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "scopes": _build_scopes(role),
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Create a signed JWT refresh token (no scopes — used only to obtain new
    access tokens).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

class TokenDecodeError(Exception):
    """Raised when a token cannot be decoded or is invalid."""


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Parameters
    ----------
    token
        Raw JWT string from the Authorization header or request body.

    Returns
    -------
    TokenPayload
        Validated payload.

    Raises
    ------
    TokenDecodeError
        If the token is malformed, expired, or has an invalid signature.
    """
    settings = get_settings()
    try:
        raw = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise TokenDecodeError(f"JWT validation failed: {exc}") from exc

    try:
        return TokenPayload(**raw)
    except Exception as exc:
        raise TokenDecodeError(f"JWT payload malformed: {exc}") from exc

"""Password hashing and session tokens (spec 018, X03).

Passwords are hashed with bcrypt (salted, cost 12); the plain password is never stored or
logged. A session is a stateless JWT (HS256) carrying the user id (`sub`) and email, signed
with `AUTH_SECRET`. Without `AUTH_SECRET` a random secret is generated once per process and
a warning is logged: tokens then die with the process, which is right for a local demo and
wrong for anything else.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final

import bcrypt
import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

SECRET_ENV: Final[str] = "AUTH_SECRET"
ALGORITHM: Final[str] = "HS256"
TOKEN_TTL: Final[timedelta] = timedelta(hours=12)
MIN_SECRET_BYTES: Final[int] = 32
"""RFC 7518 § 3.2: an HS256 key shorter than the hash output is refused."""

BCRYPT_MAX_BYTES: Final[int] = 72
"""bcrypt reads at most 72 bytes; a longer password is refused rather than truncated."""

_DUMMY_HASH: Final[bytes] = bcrypt.hashpw(b"not-a-password", bcrypt.gensalt(rounds=4))
"""Checked against when the email is unknown, so login costs a bcrypt either way."""

_dev_secret: str | None = None


class AuthEnv(BaseSettings):
    """`AUTH_SECRET` and `AUTH_REQUIRED`, from the process environment or `backend/.env`
    (the same sources as `app.commons.config.Settings`). Read per call, so a test's
    environment applies at once."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret: str = Field(default="", validation_alias="AUTH_SECRET")
    required: str = Field(default="1", validation_alias="AUTH_REQUIRED")

    @property
    def is_required(self) -> bool:
        return self.required.strip().casefold() not in {"0", "false", "no", "off"}


class InvalidTokenError(Exception):
    """The token is missing a claim, expired, or not signed with this secret."""


class TokenClaims(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    sub: str
    email: str
    exp: int


def auth_secret() -> str:
    """`AUTH_SECRET`, or a per-process random secret with a warning (dev only)."""
    global _dev_secret  # one generated secret per process, by design
    configured = AuthEnv().secret
    if configured:
        if len(configured.encode("utf-8")) < MIN_SECRET_BYTES:
            message = f"{SECRET_ENV} must be at least {MIN_SECRET_BYTES} bytes long"
            raise RuntimeError(message)
        return configured
    if _dev_secret is None:
        _dev_secret = secrets.token_urlsafe(48)
        logger.warning(
            "%s is not set: using a random secret for this process only; sessions end "
            "when it stops. Set %s in .env for anything but a local demo.",
            SECRET_ENV,
            SECRET_ENV,
        )
    return _dev_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    """True when `password` matches. An unusable hash (`local`'s `!`) never matches."""
    candidate = password.encode("utf-8")
    if password_hash is None:
        bcrypt.checkpw(candidate, _DUMMY_HASH)
        return False
    try:
        return bcrypt.checkpw(candidate, password_hash.encode("ascii"))
    except ValueError:
        return False


def create_token(user_id: str, email: str, *, secret: str, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {
        "sub": user_id,
        "email": email,
        "iat": int(issued.timestamp()),
        "exp": int((issued + TOKEN_TTL).timestamp()),
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def decode_token(token: str, *, secret: str) -> TokenClaims:
    try:
        raw = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]})
        return TokenClaims.model_validate(raw)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise InvalidTokenError(str(exc)) from exc


__all__ = [
    "ALGORITHM",
    "BCRYPT_MAX_BYTES",
    "SECRET_ENV",
    "TOKEN_TTL",
    "AuthEnv",
    "InvalidTokenError",
    "TokenClaims",
    "auth_secret",
    "create_token",
    "decode_token",
    "hash_password",
    "verify_password",
]

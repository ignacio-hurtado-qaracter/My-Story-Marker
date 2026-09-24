"""The caller's identity as a FastAPI dependency (spec 018).

`CurrentUserDep` answers who is calling. With `AUTH_REQUIRED=1` (the default) a request
without a valid `Authorization: Bearer <jwt>` is a 401. With `AUTH_REQUIRED=0` (tests, the
local visual check) a request without a token acts as the built-in `local` user, which owns
every novel the CLI creates; a token, when sent, is still verified and wins.

The token is stateless, so resolving the identity costs no query. Authorisation -- which
novels this user may see -- is the repository's (`BibleRepository.scoped_to`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.auth.security import InvalidTokenError, auth_secret, decode_token
from app.bible import LOCAL_OWNER_ID

REQUIRED_ENV: Final[str] = "AUTH_REQUIRED"
LOCAL_EMAIL: Final[str] = "local@localhost"


@dataclass(frozen=True, slots=True)
class AuthSettings:
    required: bool
    secret: str


def get_auth_settings() -> AuthSettings:
    """Read per request, so a test's environment (or override) applies at once."""
    raw = os.environ.get(REQUIRED_ENV, "1").strip().casefold()
    return AuthSettings(required=raw not in {"0", "false", "no", "off"}, secret=auth_secret())


AuthSettingsDep = Annotated[AuthSettings, Depends(get_auth_settings)]


class CurrentUser(BaseModel):
    id: str = Field(description="The `app_user` id; `local` for the built-in owner.")
    email: str


_bearer = HTTPBearer(
    auto_error=False, description="The JWT returned by `/auth/login` or `/auth/register`."
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    settings: AuthSettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> CurrentUser:
    if credentials is not None:
        try:
            claims = decode_token(credentials.credentials, secret=settings.secret)
        except InvalidTokenError as exc:
            raise _unauthorized("invalid or expired token") from exc
        return CurrentUser(id=claims.sub, email=claims.email)
    if settings.required:
        raise _unauthorized("authentication required")
    return CurrentUser(id=LOCAL_OWNER_ID, email=LOCAL_EMAIL)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

__all__ = [
    "LOCAL_EMAIL",
    "REQUIRED_ENV",
    "AuthSettings",
    "AuthSettingsDep",
    "CurrentUser",
    "CurrentUserDep",
    "get_auth_settings",
    "get_current_user",
]

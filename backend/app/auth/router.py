"""`/auth`: register, log in, who am I (spec 018).

Emails are normalised (trimmed, case-folded) before they are stored or looked up. A wrong
password and an unknown email get the same 401, and both cost one bcrypt check, so the
answer does not tell which one it was. The routes are plain `def`: bcrypt and SQLite block,
and FastAPI runs them in its threadpool.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.auth.deps import AuthSettingsDep, CurrentUserDep
from app.auth.security import (
    BCRYPT_MAX_BYTES,
    TOKEN_TTL,
    create_token,
    hash_password,
    verify_password,
)
from app.bible import AppUser
from app.reader.router import RepoDep

router = APIRouter(prefix="/auth", tags=["auth"])

Email = Annotated[
    str,
    Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$", examples=["ana@example.com"]),
]


class Credentials(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            message = f"the password may be at most {BCRYPT_MAX_BYTES} bytes in UTF-8"
            raise ValueError(message)
        return value


class UserInfo(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str = Field(description="Send as `Authorization: Bearer <token>`.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires.")
    user: UserInfo


def _token_for(user: AppUser, secret: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_token(user.id, user.email, secret=secret),
        expires_in=int(TOKEN_TTL.total_seconds()),
        user=UserInfo(id=user.id, email=user.email),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "The email is already registered."}},
)
def register(body: Credentials, repo: RepoDep, settings: AuthSettingsDep) -> TokenResponse:
    """Create a user (bcrypt-hashed password) and return a session token."""
    if repo.find_user_by_email(body.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    try:
        user = repo.create_user(email=body.email, password_hash=hash_password(body.password))
    except sqlite3.IntegrityError as exc:  # a concurrent registration of the same email
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        ) from exc
    return _token_for(user, settings.secret)


@router.post("/login", responses={401: {"description": "Wrong email or password."}})
def login(body: Credentials, repo: RepoDep, settings: AuthSettingsDep) -> TokenResponse:
    """Check the password and return a session token."""
    user = repo.find_user_by_email(body.email)
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_for(user, settings.secret)


@router.get("/me")
def me(user: CurrentUserDep) -> UserInfo:
    """The identity the token (or `AUTH_REQUIRED=0`) resolves to."""
    return UserInfo(id=user.id, email=user.email)


__all__ = ["Credentials", "TokenResponse", "UserInfo", "router"]

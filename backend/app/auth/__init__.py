"""Login with SQLite (spec 018, exam X03; closes SEC-01).

`security` hashes passwords (bcrypt) and signs session tokens (JWT HS256); `deps` turns a
request into a `CurrentUser`; `router` serves `/auth/register`, `/auth/login`, `/auth/me`.
The router is imported by `app.main` only, so this package stays importable from the
feature routers that need `CurrentUserDep`.
"""

from __future__ import annotations

from app.auth.deps import CurrentUser, CurrentUserDep, get_auth_settings, get_current_user

__all__ = ["CurrentUser", "CurrentUserDep", "get_auth_settings", "get_current_user"]

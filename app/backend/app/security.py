import time
from dataclasses import dataclass
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Header

from .config import get_settings
from .db import transaction
from .errors import ApiError

_hasher = PasswordHasher()  # Argon2id, random salt per hash
# Verified against when the username does not exist, so both cases cost the same.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    name: str
    role: str
    company: str | None
    must_change_password: bool = False


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: int) -> str:
    s = get_settings()
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + s.jwt_minutes * 60},
        s.jwt_secret,
        algorithm="HS256",
    )


def user_even_if_password_pending(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError("SESSION_EXPIRED", "Sessão expirada. Inicie sessão novamente.")
    try:
        claims = jwt.decode(
            authorization[7:],
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        raise ApiError("SESSION_EXPIRED", "Sessão expirada. Inicie sessão novamente.") from None

    # The role always comes from the database, never from the token. A disabled account is
    # locked out at once, even with a token that has not expired.
    with transaction() as cur:
        cur.execute(
            "SELECT id, username, name, role, company, must_change_password "
            "FROM app_user WHERE id = %s AND active = 1",
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ApiError("SESSION_EXPIRED", "Sessão expirada. Inicie sessão novamente.")
    return CurrentUser(**{**row, "must_change_password": bool(row["must_change_password"])})


def current_user(user: Annotated[CurrentUser, Depends(user_even_if_password_pending)]) -> CurrentUser:
    """Every endpoint but /auth/me and /auth/change-password: refused until the password is changed."""
    if user.must_change_password:
        raise ApiError(
            "PASSWORD_CHANGE_REQUIRED", "Tem de definir uma palavra-passe nova antes de continuar."
        )
    return user


def require_role(*roles: str):
    def dependency(user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise ApiError("FORBIDDEN", "Não tem permissão para esta ação.")
        return user

    return dependency

"""Airlines and accounts, for the ana_supervisor role only.

A supervisor can add airlines, add dispatcher and ANA operator accounts, disable or re-enable
them and set a new password. Supervisors themselves, controllers and handlers are not managed
here (they come from the seed), and nobody can change their own account here. Passwords set
here are temporary: the owner has to replace them at the first login. Every change is written
to audit_log.
"""

from datetime import UTC
from typing import Annotated

import pymysql
from fastapi import APIRouter, Depends

from .db import DUPLICATE_KEY, error_code, transaction
from .errors import ApiError
from .schemas import AccountIn, AccountOut, AccountPatch, AirlineIn, AirlineOut, AuditOut, PrefixIn
from .security import CurrentUser, hash_password, require_role

router = APIRouter(prefix="/api/admin")
Supervisor = Annotated[CurrentUser, Depends(require_role("ana_supervisor"))]

MANAGED_ROLES = ("despachante", "ana")
_ACCOUNT_COLUMNS = "id, username, name, email, role, company, active"


def _audit(cur, actor: CurrentUser, action: str, detail: str) -> None:
    cur.execute(
        "INSERT INTO audit_log (user_id, username, action, detail) VALUES (%s, %s, %s, %s)",
        (actor.id, actor.username, action, detail[:255]),
    )


def _account(row: dict) -> dict:
    return {**row, "id": str(row["id"]), "active": bool(row["active"])}


def _airline_rows(cur) -> list[dict]:
    cur.execute(
        "SELECT a.name, COUNT(u.id) AS dispatchers, COALESCE(SUM(u.active), 0) AS active_dispatchers "
        "FROM airline a LEFT JOIN app_user u ON u.company = a.name AND u.role = 'despachante' "
        "GROUP BY a.name ORDER BY a.name"
    )
    rows = cur.fetchall()
    cur.execute("SELECT airline, prefix FROM airline_prefix ORDER BY prefix")
    prefixes: dict[str, list[str]] = {}
    for p in cur.fetchall():
        prefixes.setdefault(p["airline"], []).append(p["prefix"])
    return [
        {
            **r,
            "dispatchers": int(r["dispatchers"]),
            "active_dispatchers": int(r["active_dispatchers"]),
            "prefixes": prefixes.get(r["name"], []),
        }
        for r in rows
    ]


def _one_airline(cur, name: str) -> dict:
    return next(r for r in _airline_rows(cur) if r["name"] == name)


def _prefix_taken(prefix: str) -> ApiError:
    return ApiError("CONFLICT", f"O prefixo {prefix} já pertence a uma companhia.")


@router.get("/airlines", response_model=list[AirlineOut])
def airlines(_: Supervisor) -> list[dict]:
    with transaction() as cur:
        return _airline_rows(cur)


@router.post("/airlines", response_model=AirlineOut, status_code=201)
def create_airline(body: AirlineIn, user: Supervisor) -> dict:
    prefixes = list(dict.fromkeys(body.prefixes))  # a prefix typed twice counts once
    try:
        with transaction() as cur:
            cur.execute("SELECT 1 FROM airline WHERE name = %s", (body.name,))
            if cur.fetchone():
                raise ApiError("CONFLICT", "Já existe uma companhia com esse nome.")
            for prefix in prefixes:
                cur.execute("SELECT airline FROM airline_prefix WHERE prefix = %s", (prefix,))
                owner = cur.fetchone()
                if owner:
                    raise ApiError("CONFLICT", f"O prefixo {prefix} já pertence a {owner['airline']}.")
            cur.execute("INSERT INTO airline (name) VALUES (%s)", (body.name,))
            for prefix in prefixes:
                cur.execute(
                    "INSERT INTO airline_prefix (prefix, airline) VALUES (%s, %s)", (prefix, body.name)
                )
            _audit(cur, user, "airline_created", f"{body.name} ({', '.join(prefixes)})")
            return _one_airline(cur, body.name)
    except pymysql.MySQLError as exc:
        if error_code(exc) == DUPLICATE_KEY:  # two supervisors at the same moment
            raise ApiError("CONFLICT", "Essa companhia ou um dos prefixos acabou de ser criado.") from None
        raise


@router.post("/airlines/{name}/prefixes", response_model=AirlineOut, status_code=201)
def add_prefix(name: str, body: PrefixIn, user: Supervisor) -> dict:
    try:
        with transaction() as cur:
            cur.execute("SELECT 1 FROM airline WHERE name = %s", (name,))
            if cur.fetchone() is None:
                raise ApiError("NOT_FOUND", "Companhia não encontrada.")
            cur.execute("INSERT INTO airline_prefix (prefix, airline) VALUES (%s, %s)", (body.prefix, name))
            _audit(cur, user, "prefix_added", f"{name}: {body.prefix}")
            return _one_airline(cur, name)
    except pymysql.MySQLError as exc:
        if error_code(exc) == DUPLICATE_KEY:
            raise _prefix_taken(body.prefix) from None
        raise


@router.delete("/airlines/{name}/prefixes/{prefix}", response_model=AirlineOut)
def remove_prefix(name: str, prefix: str, user: Supervisor) -> dict:
    with transaction() as cur:
        cur.execute("SELECT prefix FROM airline_prefix WHERE airline = %s FOR UPDATE", (name,))
        owned = [r["prefix"] for r in cur.fetchall()]
        if prefix.upper() not in owned:
            raise ApiError("NOT_FOUND", "Prefixo não encontrado.")
        if len(owned) == 1:
            raise ApiError("INVALID_INPUT", "Uma companhia tem de ter pelo menos um prefixo.")
        cur.execute("DELETE FROM airline_prefix WHERE prefix = %s AND airline = %s", (prefix.upper(), name))
        _audit(cur, user, "prefix_removed", f"{name}: {prefix.upper()}")
        return _one_airline(cur, name)


@router.get("/users", response_model=list[AccountOut])
def users(_: Supervisor) -> list[dict]:
    with transaction() as cur:
        cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app_user ORDER BY role, company, username")
        return [_account(r) for r in cur.fetchall()]


@router.post("/users", response_model=AccountOut, status_code=201)
def create_user(body: AccountIn, user: Supervisor) -> dict:
    if body.role == "despachante" and not body.company:
        raise ApiError("INVALID_INPUT", "Escolha a companhia do despachante.")
    if body.role == "ana" and body.company:
        raise ApiError("INVALID_INPUT", "Um operador da ANA não pertence a uma companhia.")
    try:
        with transaction() as cur:
            if body.role == "despachante":
                cur.execute("SELECT 1 FROM airline WHERE name = %s", (body.company,))
                if cur.fetchone() is None:
                    raise ApiError("INVALID_INPUT", "Companhia desconhecida. Crie-a primeiro.")
            cur.execute(
                "INSERT INTO app_user (username, password_hash, name, email, role, company, "
                "must_change_password) VALUES (%s, %s, %s, %s, %s, %s, 1)",
                (body.username, hash_password(body.password), body.name, body.email, body.role, body.company),
            )
            new_id = cur.lastrowid
            _audit(cur, user, "user_created", f"{body.username} ({body.role}, {body.company or 'ANA'})")
            cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app_user WHERE id = %s", (new_id,))
            return _account(cur.fetchone())
    except pymysql.MySQLError as exc:
        if error_code(exc) == DUPLICATE_KEY:
            raise ApiError("CONFLICT", "Esse nome de utilizador já existe.") from None
        raise


@router.patch("/users/{user_id}", response_model=AccountOut)
def update_user(user_id: int, body: AccountPatch, user: Supervisor) -> dict:
    if body.active is None and body.password is None:
        raise ApiError("INVALID_INPUT", "Nada para alterar.")
    with transaction() as cur:
        cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app_user WHERE id = %s FOR UPDATE", (user_id,))
        target = cur.fetchone()
        if target is None or target["role"] not in MANAGED_ROLES:
            raise ApiError("NOT_FOUND", "Conta não encontrada.")
        if target["id"] == user.id:
            raise ApiError("FORBIDDEN", "Não pode alterar a sua própria conta aqui.")
        if body.active is not None and bool(target["active"]) != body.active:
            cur.execute("UPDATE app_user SET active = %s WHERE id = %s", (int(body.active), user_id))
            _audit(cur, user, "user_enabled" if body.active else "user_disabled", target["username"])
        if body.password is not None:
            cur.execute(
                "UPDATE app_user SET password_hash = %s, must_change_password = 1 WHERE id = %s",
                (hash_password(body.password), user_id),
            )
            _audit(cur, user, "password_reset", target["username"])
        cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app_user WHERE id = %s", (user_id,))
        return _account(cur.fetchone())


@router.get("/audit", response_model=list[AuditOut])
def audit(_: Supervisor) -> list[dict]:
    with transaction() as cur:
        cur.execute("SELECT id, at, username, action, detail FROM audit_log ORDER BY id DESC LIMIT 200")
        return [{**r, "at": r["at"].replace(tzinfo=UTC)} for r in cur.fetchall()]

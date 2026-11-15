from typing import Annotated

from fastapi import APIRouter, Depends, Response

from . import reservations as svc
from .db import transaction
from .errors import ApiError
from .schemas import (
    AircraftTypeOut,
    ChangePasswordIn,
    LoginIn,
    LoginOut,
    NoticeOut,
    ReportIn,
    ReportOut,
    ReservationOut,
    StandOut,
    StandRequestIn,
    UserOut,
)
from .security import (
    CurrentUser,
    create_token,
    current_user,
    hash_password,
    require_role,
    user_even_if_password_pending,
    verify_password,
)

router = APIRouter(prefix="/api")

Authed = Annotated[CurrentUser, Depends(current_user)]
PasswordPending = Annotated[CurrentUser, Depends(user_even_if_password_pending)]
Dispatcher = Annotated[CurrentUser, Depends(require_role("despachante"))]
Ana = Annotated[CurrentUser, Depends(require_role("ana", "ana_supervisor"))]
Controller = Annotated[CurrentUser, Depends(require_role("controlador"))]
Overseer = Annotated[CurrentUser, Depends(require_role("ana", "ana_supervisor", "controlador"))]


def _user_out(u: CurrentUser) -> UserOut:
    prefixes: list[str] = []
    if u.role == "despachante":
        with transaction() as cur:
            prefixes = svc.flight_prefixes(cur, u.company)
    return UserOut(
        id=str(u.id),
        name=u.name,
        role=u.role,  # type: ignore[arg-type]
        company=u.company,
        must_change_password=u.must_change_password,
        flight_prefixes=prefixes,
    )


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    username = body.username.strip().lower()
    with transaction() as cur:
        cur.execute(
            "SELECT id, username, name, role, company, active, must_change_password, password_hash "
            "FROM app_user WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        # A disabled account fails exactly like a wrong password.
        ok = verify_password(row["password_hash"] if row else None, body.password) and bool(row["active"])
        cur.execute(
            "INSERT INTO audit_log (user_id, username, action) VALUES (%s, %s, %s)",
            (row["id"] if row and ok else None, username[:40], "login" if ok else "login_failed"),
        )
    if not ok or row is None:
        raise ApiError("INVALID_CREDENTIALS", "Utilizador ou palavra-passe incorretos.")
    user = CurrentUser(
        row["id"],
        row["username"],
        row["name"],
        row["role"],
        row["company"],
        bool(row["must_change_password"]),
    )
    return LoginOut(token=create_token(user.id), user=_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: PasswordPending) -> UserOut:
    return _user_out(user)


@router.post("/auth/change-password", response_model=UserOut)
def change_password(body: ChangePasswordIn, user: PasswordPending) -> UserOut:
    """Also the way out of the first-login lock. Needs the current password, so a stolen token alone
    is not enough to take the account over."""
    with transaction() as cur:
        cur.execute("SELECT password_hash FROM app_user WHERE id = %s FOR UPDATE", (user.id,))
        row = cur.fetchone()
        if row is None or not verify_password(row["password_hash"], body.current_password):
            raise ApiError("INVALID_CREDENTIALS", "A palavra-passe atual está incorreta.")
        if body.new_password == body.current_password:
            raise ApiError("INVALID_INPUT", "A palavra-passe nova tem de ser diferente da atual.")
        cur.execute(
            "UPDATE app_user SET password_hash = %s, must_change_password = 0 WHERE id = %s",
            (hash_password(body.new_password), user.id),
        )
        cur.execute(
            "INSERT INTO audit_log (user_id, username, action) VALUES (%s, %s, 'password_changed')",
            (user.id, user.username[:40]),
        )
    return _user_out(CurrentUser(user.id, user.username, user.name, user.role, user.company, False))


@router.get("/stands", response_model=list[StandOut])
def stands(_: Authed) -> list[dict]:
    with transaction() as cur:
        cur.execute("SELECT id, name, apron, critical, category, max_wingspan_m FROM stand ORDER BY id")
        return cur.fetchall()


@router.get("/aircraft-types", response_model=list[AircraftTypeOut])
def aircraft_types(_: Authed) -> list[dict]:
    with transaction() as cur:
        cur.execute("SELECT code, label, category, wingspan_m FROM aircraft_type ORDER BY wingspan_m")
        return cur.fetchall()


@router.get("/handlers", response_model=list[str])
def handlers(_: Authed) -> list[str]:
    with transaction() as cur:
        cur.execute("SELECT DISTINCT company FROM app_user WHERE role = 'handler' ORDER BY company")
        return [r["company"] for r in cur.fetchall()]


@router.get("/reservations", response_model=list[ReservationOut])
def reservations(user: Authed) -> list[dict]:
    return svc.list_reservations(user)


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def request_stand(body: StandRequestIn, user: Dispatcher) -> dict:
    return svc.request_stand(user, body)


@router.post("/reservations/suggestions", response_model=list[StandOut])
def suggestions(body: StandRequestIn, user: Dispatcher) -> list[dict]:
    return svc.suggest(user, body)


@router.delete("/reservations/{reservation_id}", status_code=204)
def remove_reservation(reservation_id: str, user: Ana) -> Response:
    svc.remove(user, reservation_id)
    return Response(status_code=204)


@router.get("/notices", response_model=list[NoticeOut])
def notices(user: Dispatcher) -> list[dict]:
    return svc.list_notices(user)


@router.post("/notices/dismiss", status_code=204)
def dismiss_all_notices(user: Dispatcher) -> Response:
    svc.dismiss_all_notices(user)
    return Response(status_code=204)


@router.post("/notices/{notice_id}/dismiss", status_code=204)
def dismiss_notice(notice_id: str, user: Dispatcher) -> Response:
    svc.dismiss_notice(user, notice_id)
    return Response(status_code=204)


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(body: ReportIn, user: Controller) -> dict:
    return svc.create_report(user, body.reservation_id, body.text)


@router.get("/reports", response_model=list[ReportOut])
def reports(_: Overseer) -> list[dict]:
    return svc.list_reports()

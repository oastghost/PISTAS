from typing import Annotated

from fastapi import APIRouter, Depends, Response

from . import reservations as svc
from .db import transaction
from .errors import ApiError
from .schemas import (
    AircraftTypeOut,
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
from .security import CurrentUser, create_token, current_user, require_role, verify_password

router = APIRouter(prefix="/api")

Authed = Annotated[CurrentUser, Depends(current_user)]
Dispatcher = Annotated[CurrentUser, Depends(require_role("despachante"))]
Ana = Annotated[CurrentUser, Depends(require_role("ana"))]
Controller = Annotated[CurrentUser, Depends(require_role("controlador"))]
Overseer = Annotated[CurrentUser, Depends(require_role("ana", "controlador"))]


def _user_out(u: CurrentUser) -> UserOut:
    return UserOut(id=str(u.id), name=u.name, role=u.role, company=u.company)  # type: ignore[arg-type]


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    username = body.username.strip().lower()
    with transaction() as cur:
        cur.execute(
            "SELECT id, username, name, role, company, password_hash FROM app_user WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        ok = verify_password(row["password_hash"] if row else None, body.password)
        cur.execute(
            "INSERT INTO audit_log (user_id, username, action) VALUES (%s, %s, %s)",
            (row["id"] if row and ok else None, username[:40], "login" if ok else "login_failed"),
        )
    if not ok or row is None:
        raise ApiError("INVALID_CREDENTIALS", "Utilizador ou palavra-passe incorretos.")
    user = CurrentUser(row["id"], row["username"], row["name"], row["role"], row["company"])
    return LoginOut(token=create_token(user.id), user=_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: Authed) -> UserOut:
    return _user_out(user)


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


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(body: ReportIn, user: Controller) -> dict:
    return svc.create_report(user, body.reservation_id, body.text)


@router.get("/reports", response_model=list[ReportOut])
def reports(_: Overseer) -> list[dict]:
    return svc.list_reports()

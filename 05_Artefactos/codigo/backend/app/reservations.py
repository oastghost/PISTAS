"""Reservation rules. Every write is one transaction and the database decides conflicts.

The checks done in Python before writing are an optimisation and give nicer messages. The
guarantee is `stand_block UNIQUE (stand_id, occupied WITHOUT OVERLAPS)`.
"""

import random
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

import pymysql

from . import solver
from .config import get_settings
from .db import DUPLICATE_KEY, RETRYABLE, error_code, transaction
from .errors import ApiError
from .schemas import StandRequestIn
from .security import CurrentUser

FLIGHT_RE = re.compile(r"^[A-Z0-9]{2,10}$")
MAX_STAY = timedelta(hours=72)
MAX_ATTEMPTS = 6

_RESERVATION_COLUMNS = (
    "id, request_id, stand_id, flight_number, company, aircraft_type, "
    "starts_at AS start, ends_at AS end, status, handler"
)


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def _minutes(value: datetime) -> int:
    """Minutes since the epoch for a naive UTC datetime."""
    return int(value.replace(tzinfo=UTC).timestamp() // 60)


def _aware(row: dict) -> dict:
    return {
        **row,
        "start": row["start"].replace(tzinfo=UTC),
        "end": row["end"].replace(tzinfo=UTC),
    }


def with_retry(operation):
    """Runs `operation` (one whole transaction), repeating it when Galera or InnoDB asks.

    Error 1213 is also how a lost cross-node race looks. Repeating the same request either
    wins or gets a true overlap error, so the dispatcher never sees a false refusal.
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            return operation()
        except pymysql.MySQLError as exc:
            if error_code(exc) not in RETRYABLE:
                raise
            time.sleep(random.uniform(0.01, 0.05) * (attempt + 1))
    raise ApiError("UNAVAILABLE", "O sistema está ocupado. Tente novamente dentro de instantes.")


def list_reservations(user: CurrentUser) -> list[dict]:
    sql = f"SELECT {_RESERVATION_COLUMNS} FROM reservation"
    args: tuple = ()
    if user.role == "handler":
        # A handling company only sees requests addressed to it.
        sql += " WHERE handler = %s"
        args = (user.company,)
    with transaction() as cur:
        cur.execute(sql + " ORDER BY starts_at, id", args)
        return [_aware(r) for r in cur.fetchall()]


def _validate(cur, user: CurrentUser, req: StandRequestIn) -> tuple[dict, dict, str]:
    flight = req.flight_number.upper()
    if not FLIGHT_RE.match(flight):
        raise ApiError("INVALID_INPUT", "Número de voo inválido.")
    if req.end <= req.start or req.end - req.start > MAX_STAY:
        raise ApiError("INVALID_INPUT", "Período inválido.")

    cur.execute("SELECT code, wingspan_m FROM aircraft_type WHERE code = %s", (req.aircraft_type,))
    aircraft = cur.fetchone()
    if aircraft is None:
        raise ApiError("INVALID_INPUT", "Tipo de aeronave desconhecido.")

    cur.execute("SELECT id, name, critical, max_wingspan_m FROM stand WHERE id = %s", (req.stand_id,))
    stand = cur.fetchone()
    if stand is None:
        raise ApiError("INVALID_INPUT", "Stand desconhecido.")

    if req.handler:
        cur.execute("SELECT 1 FROM app_user WHERE role = 'handler' AND company = %s LIMIT 1", (req.handler,))
        if cur.fetchone() is None:
            raise ApiError("INVALID_INPUT", "Empresa de assistência em terra desconhecida.")
    return aircraft, stand, flight


def _create(user: CurrentUser, req: StandRequestIn) -> dict:
    gap = timedelta(minutes=get_settings().turnaround_minutes)
    starts, ends = _naive_utc(req.start), _naive_utc(req.end)

    with transaction() as cur:
        # Idempotency: the same request id returns the first result and creates nothing.
        cur.execute(
            f"SELECT {_RESERVATION_COLUMNS} FROM reservation WHERE request_id = %s", (req.request_id,)
        )
        existing = cur.fetchone()
        if existing:
            if existing["company"] != user.company:
                raise ApiError("INVALID_INPUT", "Identificador de pedido já utilizado.")
            return _aware(existing)

        aircraft, stand, flight = _validate(cur, user, req)
        if float(stand["max_wingspan_m"]) < float(aircraft["wingspan_m"]):
            raise ApiError(
                "STAND_TOO_SMALL",
                f"O {stand['name']} não aceita esta aeronave (limite {stand['critical']}).",
            )

        cur.execute(
            "SELECT 1 FROM removed_assignment WHERE company = %s AND flight_number = %s "
            "AND stand_id = %s LIMIT 1",
            (user.company, flight, stand["id"]),
        )
        if cur.fetchone():
            raise ApiError(
                "STAND_UNAVAILABLE",
                f"O {stand['name']} foi retirado a este voo pela ANA e não pode voltar a ser pedido.",
            )

        reservation_id = str(uuid.uuid4())
        occupied_to = ends + gap
        cur.execute(
            "SELECT 1 FROM stand_block WHERE stand_id = %s AND occupied_from < %s "
            "AND occupied_to > %s LIMIT 1",
            (stand["id"], occupied_to, starts),
        )
        if cur.fetchone():
            raise ApiError("STAND_UNAVAILABLE", f"O {stand['name']} não está disponível neste período.")

        cur.execute(
            "INSERT INTO reservation (id, request_id, stand_id, flight_number, company, "
            "aircraft_type, starts_at, ends_at, handler, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                reservation_id,
                req.request_id,
                stand["id"],
                flight,
                user.company,
                req.aircraft_type,
                starts,
                ends,
                req.handler or None,
                user.id,
            ),
        )
        try:
            cur.execute(
                "INSERT INTO stand_block (reservation_id, stand_id, occupied_from, occupied_to) "
                "VALUES (%s, %s, %s, %s)",
                (reservation_id, stand["id"], starts, occupied_to),
            )
        except pymysql.IntegrityError as exc:
            if error_code(exc) == DUPLICATE_KEY:
                # Somebody committed an overlapping block between our check and our write.
                raise ApiError(
                    "STAND_UNAVAILABLE", f"O {stand['name']} não está disponível neste período."
                ) from None
            raise

        cur.execute(f"SELECT {_RESERVATION_COLUMNS} FROM reservation WHERE id = %s", (reservation_id,))
        return _aware(cur.fetchone())


def request_stand(user: CurrentUser, req: StandRequestIn) -> dict:
    try:
        return with_retry(lambda: _create(user, req))
    except pymysql.IntegrityError as exc:
        # Two requests with the same id raced: the loser reads the winner's reservation.
        if error_code(exc) == DUPLICATE_KEY and "uq_reservation_request" in str(exc):
            return with_retry(lambda: _create(user, req))
        raise


def suggest(user: CurrentUser, req: StandRequestIn) -> list[dict]:
    gap = timedelta(minutes=get_settings().turnaround_minutes)
    starts, ends = _naive_utc(req.start), _naive_utc(req.end)
    flight = req.flight_number.upper()

    with transaction() as cur:
        cur.execute("SELECT wingspan_m FROM aircraft_type WHERE code = %s", (req.aircraft_type,))
        aircraft = cur.fetchone()
        if aircraft is None or req.end <= req.start:
            raise ApiError("INVALID_INPUT", "Dados do pedido inválidos.")
        cur.execute("SELECT id, name, apron, critical, category, max_wingspan_m FROM stand")
        stands = cur.fetchall()
        cur.execute(
            "SELECT stand_id, occupied_from, occupied_to FROM stand_block "
            "WHERE occupied_from < %s AND occupied_to > %s",
            (ends + gap, starts),
        )
        blocks = [
            solver.Block(r["stand_id"], _minutes(r["occupied_from"]), _minutes(r["occupied_to"]))
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT stand_id FROM removed_assignment WHERE company = %s AND flight_number = %s",
            (user.company, flight),
        )
        banned = frozenset(r["stand_id"] for r in cur.fetchall())

    try:
        ids = solver.propose(
            [solver.StandInfo(s["id"], s["apron"], float(s["max_wingspan_m"])) for s in stands],
            blocks,
            solver.Flight(
                id=flight,
                wingspan_m=float(aircraft["wingspan_m"]),
                start=_minutes(starts),
                end=_minutes(ends + gap),
                wanted=req.stand_id,
                banned=banned,
            ),
        )
    except solver.SolverError:
        # Nothing was written, so failing cleanly costs the dispatcher only a retry.
        raise ApiError("UNAVAILABLE", "Não foi possível calcular alternativas agora.") from None
    by_id = {s["id"]: s for s in stands}
    return [by_id[i] for i in ids]


def _remove(user: CurrentUser, reservation_id: str) -> None:
    with transaction() as cur:
        cur.execute(
            "SELECT id, stand_id, flight_number, company, status FROM reservation WHERE id = %s FOR UPDATE",
            (reservation_id,),
        )
        row = cur.fetchone()
        if row is None or row["status"] != "approved":
            raise ApiError("NOT_FOUND", "Reserva não encontrada.")
        cur.execute("SELECT name FROM stand WHERE id = %s", (row["stand_id"],))
        stand_name = cur.fetchone()["name"]

        # Removal, notice and audit entry are one transaction: all or nothing.
        cur.execute("UPDATE reservation SET status = 'removed' WHERE id = %s", (row["id"],))
        cur.execute("DELETE FROM stand_block WHERE reservation_id = %s", (row["id"],))
        cur.execute(
            "INSERT INTO removed_assignment (company, flight_number, stand_id) VALUES (%s, %s, %s)",
            (row["company"], row["flight_number"], row["stand_id"]),
        )
        cur.execute(
            "INSERT INTO notice (id, reservation_id, company, message) VALUES (%s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                row["id"],
                row["company"],
                f"A ANA removeu a alocação do voo {row['flight_number']} no {stand_name}. "
                f"Para esclarecimentos contacte a ANA: {get_settings().ana_phone}.",
            ),
        )
        cur.execute(
            "INSERT INTO audit_log (user_id, username, action, detail) VALUES (%s, %s, 'ana_removal', %s)",
            (user.id, user.username, f"reservation {row['id']} flight {row['flight_number']}"),
        )


def remove(user: CurrentUser, reservation_id: str) -> None:
    with_retry(lambda: _remove(user, reservation_id))


def list_notices(user: CurrentUser) -> list[dict]:
    with transaction() as cur:
        cur.execute(
            "SELECT id, reservation_id, company, message, created_at FROM notice "
            "WHERE company = %s ORDER BY created_at, id",
            (user.company,),
        )
        return [{**r, "created_at": r["created_at"].replace(tzinfo=UTC)} for r in cur.fetchall()]


def create_report(user: CurrentUser, reservation_id: str, text: str) -> dict:
    report_id = str(uuid.uuid4())
    with transaction() as cur:
        cur.execute("SELECT 1 FROM reservation WHERE id = %s", (reservation_id,))
        if cur.fetchone() is None:
            raise ApiError("NOT_FOUND", "Reserva não encontrada.")
        cur.execute(
            "INSERT INTO report (id, reservation_id, author_id, text) VALUES (%s, %s, %s, %s)",
            (report_id, reservation_id, user.id, text),
        )
        cur.execute(
            "SELECT r.id, r.reservation_id, r.text, u.name AS author, r.created_at "
            "FROM report r JOIN app_user u ON u.id = r.author_id WHERE r.id = %s",
            (report_id,),
        )
        row = cur.fetchone()
    return {**row, "created_at": row["created_at"].replace(tzinfo=UTC)}


def list_reports() -> list[dict]:
    with transaction() as cur:
        cur.execute(
            "SELECT r.id, r.reservation_id, r.text, u.name AS author, r.created_at "
            "FROM report r JOIN app_user u ON u.id = r.author_id ORDER BY r.created_at, r.id"
        )
        return [{**r, "created_at": r["created_at"].replace(tzinfo=UTC)} for r in cur.fetchall()]

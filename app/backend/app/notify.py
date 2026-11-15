"""E-mail alerts to ANA when a controller reports a flight.

Transactional outbox: `enqueue` writes one row per ANA recipient in the same transaction as the
report. `deliver_pending` sends them and runs in a worker thread inside every backend. Sending
never sits in the request path, so a dead SMTP server cannot make a report fail or slow down.

Several backends poll the same table. A row is claimed with a conditional UPDATE that pushes
`next_try_at` into the future (a lease), so only one worker wins it. On Galera a concurrent claim
from another node fails certification (deadlock error) and counts as lost. Delivery is
at-least-once: a crash between sending and marking the row can repeat one e-mail, never lose it.
"""

import logging
import smtplib
import socket
import threading
from email.message import EmailMessage

import pymysql

from .config import get_settings
from .db import DEADLOCK, error_code, transaction

log = logging.getLogger("pistas.notify")

LEASE_SECONDS = 60
BATCH = 25

_wake = threading.Event()


def enabled() -> bool:
    return bool(get_settings().smtp_host)


def kick() -> None:
    """Wakes the local worker right after a report is committed. Other backends poll."""
    _wake.set()


def _line(value: str) -> str:
    """One line, safe for a mail header."""
    return " ".join(value.split())


def enqueue(cur, report_id: str, reservation_id: str, author: str, text: str) -> int:
    """Inside the report's transaction. Returns how many e-mails were queued."""
    if not enabled():
        return 0
    cur.execute(
        "SELECT r.registration, r.flight_number, r.origin, r.company, r.aircraft_type, a.label AS aircraft_label, "
        "r.stand_id, s.name AS stand_name, s.apron, r.starts_at, r.ends_at "
        "FROM reservation r "
        "JOIN stand s ON s.id = r.stand_id "
        "JOIN aircraft_type a ON a.code = r.aircraft_type "
        "WHERE r.id = %s",
        (reservation_id,),
    )
    res = cur.fetchone()
    cur.execute(
        "SELECT email FROM app_user "
        "WHERE role IN ('ana', 'ana_supervisor') AND active = 1 AND email IS NOT NULL ORDER BY id"
    )
    recipients = [row["email"] for row in cur.fetchall()]
    if res is None or not recipients:
        return 0

    registration = _line(res["registration"])
    flight = _line(res["flight_number"])
    subject = (
        f"[PISTAS] Stand incorreto reportado: {registration}, {res['aircraft_type']}, stand {res['stand_id']}"
    )
    body = (
        "Um controlador reportou um problema com a alocação de um stand.\n\n"
        f"Matrícula:   {registration} ({_line(res['company'])})\n"
        f"Voo chegada: {flight}, origem {res['origin']}\n"
        f"Aeronave:    {res['aircraft_type']} ({res['aircraft_label']})\n"
        f"Stand/gate:  {res['stand_name']} (placa {res['apron']})\n"
        f"Horário UTC: {res['starts_at']:%Y-%m-%d %H:%M} a {res['ends_at']:%Y-%m-%d %H:%M}\n"
        f"Reportado por: {_line(author)}\n\n"
        f"Descrição:\n{text}\n\n"
        "Reveja o plano na área da ANA da PISTAS.\n"
    )
    cur.executemany(
        "INSERT INTO email_outbox (report_id, recipient, subject, body) VALUES (%s, %s, %s, %s)",
        [(report_id, to, subject, body) for to in recipients],
    )
    return len(recipients)


def _send(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


def _claim(row_id: int) -> dict | None:
    """Wins the row or returns None. Exactly one worker gets a given row per lease."""
    try:
        with transaction() as cur:
            cur.execute(
                "UPDATE email_outbox SET attempts = attempts + 1, "
                "next_try_at = NOW() + INTERVAL %s SECOND "
                "WHERE id = %s AND status = 'pending' AND next_try_at <= NOW()",
                (LEASE_SECONDS, row_id),
            )
            if cur.rowcount != 1:
                return None
            cur.execute(
                "SELECT id, recipient, subject, body, attempts FROM email_outbox WHERE id = %s", (row_id,)
            )
            return cur.fetchone()
    except pymysql.MySQLError as exc:
        if error_code(exc) == DEADLOCK:
            return None  # another node claimed it first
        raise


def deliver_pending() -> int:
    """Sends what is due. Returns how many e-mails were sent. Never raises for a bad SMTP server."""
    s = get_settings()
    with transaction() as cur:
        cur.execute(
            "SELECT id FROM email_outbox WHERE status = 'pending' AND next_try_at <= NOW() "
            "ORDER BY id LIMIT %s",
            (BATCH,),
        )
        due = [r["id"] for r in cur.fetchall()]
    sent = 0
    for row_id in due:
        row = _claim(row_id)
        if row is None:
            continue
        try:
            _send(row["recipient"], row["subject"], row["body"])
        except Exception as exc:  # SMTP down, refused, timeout: retry later with backoff
            failed = row["attempts"] >= s.mail_max_attempts
            backoff = min(15 * 2 ** (row["attempts"] - 1), 300)
            with transaction() as cur:
                cur.execute(
                    "UPDATE email_outbox SET status = %s, last_error = %s, "
                    "next_try_at = NOW() + INTERVAL %s SECOND WHERE id = %s",
                    ("failed" if failed else "pending", str(exc)[:255], backoff, row_id),
                )
            log.warning(
                "e-mail %s to %s failed (attempt %s): %s", row_id, row["recipient"], row["attempts"], exc
            )
            continue
        with transaction() as cur:
            cur.execute(
                "UPDATE email_outbox SET status = 'sent', sent_at = NOW(), sent_by = %s, last_error = NULL "
                "WHERE id = %s",
                (socket.gethostname()[:64], row_id),
            )
        sent += 1
    return sent


def run_worker(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            while deliver_pending() >= BATCH and not stop.is_set():
                pass  # a full batch means there is probably more
        except Exception:
            log.exception("outbox worker iteration failed")  # database down: try again next tick
        _wake.wait(get_settings().mail_poll_seconds)
        _wake.clear()

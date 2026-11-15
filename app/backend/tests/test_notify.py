"""E-mail alerts to ANA: outbox, delivery, failure handling, no duplicates between workers."""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email import message_from_bytes, message_from_string
from email.header import decode_header, make_header

import pytest

from app import notify
from app.config import get_settings
from app.db import connect

H = timedelta(hours=1)
ANA_RECIPIENTS = {
    "ana@pistas.test",
    "ana2@pistas.test",
    "ana3@pistas.test",
    "supervisor@pistas.test",
}
N = len(ANA_RECIPIENTS)


class SmtpSink:
    """Just enough SMTP to accept messages. python 3.12 no longer ships smtpd."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []  # (recipient, raw message)
        self._lock = threading.Lock()
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(64)
        self.port = self._sock.getsockname()[1]
        self._stopped = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._stopped:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        f = conn.makefile("rwb")

        def say(line: str) -> None:
            f.write(line.encode() + b"\r\n")
            f.flush()

        say("220 sink ready")
        rcpt = ""
        for raw in f:
            cmd = raw.decode(errors="replace").strip()
            verb = cmd.upper()
            if verb.startswith(("EHLO", "HELO")):
                say("250 sink")
            elif verb.startswith("RCPT TO:"):
                rcpt = cmd.split(":", 1)[1].strip().strip("<>")
                say("250 ok")
            elif verb.startswith("DATA"):
                say("354 go")
                lines = []
                for data_line in f:
                    text = data_line.decode("latin-1")  # lossless: bytes round-trip
                    if text == ".\r\n":
                        break
                    lines.append(text)
                with self._lock:
                    self.messages.append((rcpt, "".join(lines)))
                say("250 queued")
            elif verb.startswith("QUIT"):
                say("221 bye")
                break
            else:
                say("250 ok")
        conn.close()

    def close(self) -> None:
        self._stopped = True
        self._sock.close()


def _use_smtp(monkeypatch, port: int | None) -> None:
    if port is None:
        monkeypatch.setenv("SMTP_HOST", "")
    else:
        monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
        monkeypatch.setenv("SMTP_PORT", str(port))
    get_settings.cache_clear()


@pytest.fixture
def sink(monkeypatch):
    s = SmtpSink()
    _use_smtp(monkeypatch, s.port)
    yield s
    s.close()
    monkeypatch.undo()
    get_settings.cache_clear()


def _rows(sql: str, *args) -> list[dict]:
    conn = connect(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())
    finally:
        conn.close()


def _make_report(login, day, *, stand="114", flight="TP1234", aircraft="A320", text="Stand ocupado"):
    tap, atc = login("tap"), login("atc")
    res = tap.bid(stand, start=day + 8 * H, flight=flight, aircraft=aircraft).json()
    r = atc.http.post("/api/reports", json={"reservationId": res["id"], "text": text})
    assert r.status_code == 201, r.text
    return r.json()


def _subject(raw: str) -> str:
    return str(make_header(decode_header(message_from_string(raw)["Subject"])))


def test_report_queues_one_email_per_ana_user(login, day, sink):
    report = _make_report(login, day)
    rows = _rows("SELECT recipient, status FROM email_outbox WHERE report_id = %s", report["id"])
    assert {r["recipient"] for r in rows} == ANA_RECIPIENTS
    assert {r["status"] for r in rows} == {"pending"}


def test_email_carries_flight_aircraft_and_stand(login, day, sink):
    report = _make_report(login, day, stand="114", flight="TP1234", aircraft="A320", text="Voo no stand errado")
    registration = report["registration"]
    assert notify.deliver_pending() == N
    assert {to for to, _ in sink.messages} == ANA_RECIPIENTS
    _, raw = sink.messages[0]
    subject = _subject(raw)
    assert registration in subject and "A320" in subject and "114" in subject
    msg = message_from_bytes(raw.encode("latin-1"))
    body = msg.get_payload(decode=True).decode("utf-8")
    assert registration in body and "TP1234" in body and "LEMD" in body
    assert "A320" in body and "Voo no stand errado" in body
    assert {r["status"] for r in _rows("SELECT status FROM email_outbox")} == {"sent"}


def test_report_api_exposes_flight_aircraft_and_stand(login, day, sink):
    report = _make_report(login, day, stand="114", flight="TP1234", aircraft="A320")
    assert (report["flightNumber"], report["aircraftType"], report["standId"]) == ("TP1234", "A320", "114")


def test_smtp_down_does_not_fail_the_report_and_is_retried(login, day, monkeypatch):
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    port = dead.getsockname()[1]
    dead.close()  # nothing listens here any more
    _use_smtp(monkeypatch, port)
    try:
        _make_report(login, day)  # still 201
        assert notify.deliver_pending() == 0
        rows = _rows("SELECT status, attempts, last_error FROM email_outbox")
        assert len(rows) == N
        assert {r["status"] for r in rows} == {"pending"}
        assert all(r["attempts"] == 1 and r["last_error"] for r in rows)

        s = SmtpSink()
        try:
            _use_smtp(monkeypatch, s.port)
            _rows("UPDATE email_outbox SET next_try_at = NOW() - INTERVAL 1 SECOND")  # backoff elapsed
            assert notify.deliver_pending() == N
            assert {to for to, _ in s.messages} == ANA_RECIPIENTS
        finally:
            s.close()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_gives_up_after_max_attempts(login, day, monkeypatch):
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    port = dead.getsockname()[1]
    dead.close()
    _use_smtp(monkeypatch, port)
    monkeypatch.setenv("MAIL_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()
    try:
        _make_report(login, day)
        for _ in range(2):
            notify.deliver_pending()
            _rows("UPDATE email_outbox SET next_try_at = NOW() - INTERVAL 1 SECOND")
        assert {r["status"] for r in _rows("SELECT status FROM email_outbox")} == {"failed"}
        assert notify.deliver_pending() == 0
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_concurrent_workers_send_each_email_exactly_once(login, day, sink):
    tap, atc = login("tap"), login("atc")
    stands = ["104", "105", "106", "107", "114", "115", "116", "117", "122", "123"]
    for i, stand in enumerate(stands):
        res = tap.bid(stand, start=day + 8 * H, flight=f"TP{i:03d}")
        assert res.status_code == 201, res.text
        atc.http.post("/api/reports", json={"reservationId": res.json()["id"], "text": f"r{i}"})
    total = len(_rows("SELECT id FROM email_outbox"))
    assert total == N * len(stands)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: notify.deliver_pending(), range(8)))
    # a worker may lose a lease race and leave a row for the next pass
    while notify.deliver_pending():
        pass

    assert len(sink.messages) == total
    assert len({(to, _subject(raw), raw.split("\r\n\r\n")[-1]) for to, raw in sink.messages}) == total
    assert {r["status"] for r in _rows("SELECT status FROM email_outbox")} == {"sent"}


def test_alerts_off_without_smtp_host(login, day, monkeypatch):
    _use_smtp(monkeypatch, None)
    try:
        report = _make_report(login, day)
        assert report["flightNumber"] == "TP1234"
        assert _rows("SELECT id FROM email_outbox") == []
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

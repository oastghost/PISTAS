"""E-mail alerts at scale and under a mail outage, against the real stack (T9, T10).

Needs the Mailpit container from docker-compose.yml (API on http://localhost:8025).
T9  A burst of reports from many controllers: every ANA account gets exactly one e-mail per
    report, none lost, none duplicated, although the 3 backends all run a delivery worker.
T10 The mail server is down during the burst: every report is still accepted, and everything
    is delivered, once, after the server returns.
"""

import os
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from .conftest import Client, compose, payload, send_with_retry, sql, wait_for

MAILPIT = os.environ.get("PISTAS_MAILPIT", "http://localhost:8025")
ANA_ACCOUNTS = 4  # ana, ana2, ana3 and supervisor in app/seed.py
REPORTS = int(os.environ.get("PISTAS_MAIL_REPORTS", "150"))
WORKERS = 24


def mailpit_total() -> int:
    return httpx.get(f"{MAILPIT}/api/v1/messages?limit=1", timeout=10).json()["total"]


def mailpit_messages() -> list[dict]:
    out: list[dict] = []
    while len(out) < mailpit_total():
        page = httpx.get(f"{MAILPIT}/api/v1/messages?limit=500&start={len(out)}", timeout=30).json()
        if not page["messages"]:
            break
        out.extend(page["messages"])
    return out


@pytest.fixture(autouse=True)
def mailbox():
    compose("start", "mailpit")
    wait_for(lambda: mailpit_total() >= 0, 60, "mailpit up")
    httpx.delete(f"{MAILPIT}/api/v1/messages", timeout=30)
    yield
    compose("start", "mailpit")


@pytest.fixture(scope="module")
def controllers(cluster_ready) -> list[Client]:
    return [Client("atc") for _ in range(4)]


def make_reservations(tap: Client, n: int) -> list[dict]:
    """Reservations are made one by one: this test is about reports, not about the bid rules."""
    out = []
    for i in range(n):
        r = send_with_retry(tap, payload(i))
        assert r.status_code == 201, r.text
        out.append(r.json())
    return out


def burst(controllers: list[Client], reservations: list[dict]) -> list[float]:
    """All reports at once through nginx. Returns each request's latency in seconds."""

    def report(i: int) -> float:
        t0 = time.perf_counter()
        for _ in range(8):
            r = controllers[i % len(controllers)].http.post(
                "/api/reports", json={"reservationId": reservations[i]["id"], "text": f"Stand errado {i}"}
            )
            if r.status_code < 500:
                break
            time.sleep(0.5)
        assert r.status_code == 201, r.text
        return time.perf_counter() - t0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(report, range(len(reservations))))


def outbox(where: str) -> int:
    return int(sql("galera1", f"SELECT COUNT(*) FROM pistas.email_outbox WHERE {where}")[1].splitlines()[-1])


def assert_exactly_once(reservations: list[dict]) -> None:
    expected = len(reservations) * ANA_ACCOUNTS
    wait_for(lambda: mailpit_total() >= expected, 180, f"{expected} e-mails in the mailbox", 2)
    time.sleep(10)  # a duplicate would show up now
    messages = mailpit_messages()
    seen = Counter((m["To"][0]["Address"], m["Subject"]) for m in messages)
    dupes = {k: v for k, v in seen.items() if v > 1}
    assert not dupes, f"duplicated e-mails: {list(dupes.items())[:5]}"
    assert len(messages) == expected
    for res in reservations:
        flight = res["registration"]
        assert sum(1 for (_, subject) in seen if flight in subject) == ANA_ACCOUNTS, flight
    assert outbox("status = 'sent'") == expected
    assert outbox("status <> 'sent'") == 0


def test_t9_burst_of_reports_one_email_per_ana_account(tap, controllers):
    reservations = make_reservations(tap, REPORTS)
    t0 = time.perf_counter()
    latencies = sorted(burst(controllers, reservations))
    took = time.perf_counter() - t0
    assert_exactly_once(reservations)

    by_backend = sql("galera1", "SELECT sent_by, COUNT(*) FROM pistas.email_outbox GROUP BY sent_by")[1]
    print(
        f"\nT9: {REPORTS} reports -> {REPORTS * ANA_ACCOUNTS} e-mails, all delivered once."
        f"\n    report latency p50 {statistics.median(latencies) * 1000:.0f} ms, "
        f"p95 {latencies[int(len(latencies) * 0.95) - 1] * 1000:.0f} ms, "
        f"{REPORTS / took:.0f} reports/s accepted"
        f"\n    delivered by backend:\n{by_backend}"
    )
    assert len(by_backend.splitlines()) >= 2, "the workers should share the load"


def test_t10_mail_server_down_during_burst(tap, controllers):
    reservations = make_reservations(tap, REPORTS)
    compose("stop", "mailpit")
    latencies = burst(controllers, reservations)  # every report must still be accepted
    assert outbox("status = 'pending'") > 0
    assert outbox("status = 'sent'") == 0
    compose("start", "mailpit")
    wait_for(lambda: mailpit_total() >= 0, 60, "mailpit back")
    # Retry backoff starts at 15 s, so allow a few rounds.
    assert_exactly_once(reservations)
    print(
        f"\nT10: {REPORTS} reports accepted with the mail server down (max {max(latencies):.2f} s), "
        f"{REPORTS * ANA_ACCOUNTS} e-mails delivered once after it returned."
    )

"""Test setup: a throwaway database `pistas_test` on the dev MariaDB, and a real HTTP server.

Real HTTP matters for the concurrency tests: they must go through the same path a browser does.
Needs the dev database running (docker compose up -d db) and a filled-in .env.
"""

import os
import socket
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pymysql
import pytest
import uvicorn

from app.config import Settings, get_settings

TEST_DB = "pistas_test"
TEST_PASSWORD = "test-" + uuid.uuid4().hex  # never used outside this test database


def _configure() -> Settings:
    base = Settings()  # reads .env
    os.environ.update(
        DB_NAME=TEST_DB,
        DB_USER="root",
        DB_PASSWORD=base.db_root_password,
        SEED_PASSWORD=TEST_PASSWORD,
        ANA_PHONE="+351 000 000 000 (teste)",
    )
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def server():
    settings = _configure()
    admin = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user="root",
        password=settings.db_root_password,
        autocommit=True,
    )
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        cur.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4")
    admin.close()

    from app.migrate import migrate
    from app.seed import seed

    migrate()
    seed(TEST_PASSWORD)

    from app.main import create_app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def clean_reservations(server):
    """Every test starts without reservations. Reference data and accounts stay."""
    from app.db import connect

    conn = connect(autocommit=True)
    with conn.cursor() as cur:
        for table in ("notice", "report", "stand_block", "removed_assignment", "reservation", "audit_log"):
            cur.execute(f"DELETE FROM {table}")
    conn.close()


class Client:
    def __init__(self, base: str, username: str):
        self.http = httpx.Client(base_url=base, timeout=30)
        resp = self.http.post("/api/auth/login", json={"username": username, "password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text
        self.user = resp.json()["user"]
        self.http.headers["Authorization"] = f"Bearer {resp.json()['token']}"

    def bid(
        self,
        stand: str,
        *,
        start: datetime,
        hours: float = 2,
        flight: str = "TP1",
        aircraft: str = "A320",
        handler: str | None = None,
        request_id: str | None = None,
    ):
        return self.http.post(
            "/api/reservations",
            json={
                "requestId": request_id or str(uuid.uuid4()),
                "standId": stand,
                "flightNumber": flight,
                "aircraftType": aircraft,
                "start": start.isoformat(),
                "end": (start + timedelta(hours=hours)).isoformat(),
                "handler": handler,
            },
        )


@pytest.fixture
def login(server):
    def _login(username: str) -> Client:
        return Client(server, username)

    return _login


@pytest.fixture
def day():
    """A fixed, future UTC day so tests never depend on the clock."""
    return datetime(2030, 6, 15, 0, 0, tzinfo=UTC)

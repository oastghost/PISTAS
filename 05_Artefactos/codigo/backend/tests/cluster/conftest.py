"""Fault tests against the real stack: nginx, 3 backends, 3 Galera nodes, in Docker.

Opt in with PISTAS_CLUSTER=1 and have `docker compose up -d` running in 05_Artefactos/codigo.
They stop, kill and disconnect containers, so never point them at anything you care about.
Run from a shell where `docker` is on PATH:   PISTAS_CLUSTER=1 python -m pytest tests/cluster -s
"""

import json
import os
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import ROOT, Settings

PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "codigo")
URL = os.environ.get("PISTAS_URL", "https://localhost:8443")
NODES = ("galera1", "galera2", "galera3")
SETTINGS = Settings()
STANDS = [s["id"] for s in json.loads((ROOT / "db" / "seed" / "stands.json").read_text("utf-8"))]
DAY = datetime(2031, 3, 10, tzinfo=UTC)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("PISTAS_CLUSTER") == "1":
        return
    skip = pytest.mark.skip(reason="set PISTAS_CLUSTER=1 to run the cluster fault tests")
    here = os.path.dirname(__file__)
    for item in items:
        # This hook sees every collected test, not only the ones in this directory.
        if str(item.path).startswith(here):
            item.add_marker(skip)


def docker(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def compose(*args: str) -> subprocess.CompletedProcess:
    return docker("compose", *args)


def sql(node: str, query: str) -> tuple[int, str]:
    """Runs a statement on one database node as root. Returns (exit code, output or error)."""
    r = compose(
        "exec", "-T", node, "mariadb", "-uroot", f"-p{SETTINGS.db_root_password}", "-N", "-B", "-e", query
    )
    return r.returncode, (r.stdout if r.returncode == 0 else r.stderr).strip()


def scalar(node: str, query: str) -> str:
    code, out = sql(node, query)
    assert code == 0, out
    return out.splitlines()[-1] if out else ""


def wait_for(condition: Callable[[], bool], timeout: float, what: str, interval: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if condition():
                return
        except Exception:
            pass
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout:.0f}s waiting for: {what}")


def cluster_size(node: str = "galera1") -> int:
    code, out = sql(node, "SHOW STATUS LIKE 'wsrep_cluster_size'")
    return int(out.split()[-1]) if code == 0 and out else 0


def synced(node: str) -> bool:
    code, out = sql(node, "SHOW STATUS LIKE 'wsrep_local_state_comment'")
    return code == 0 and out.endswith("Synced")


def container_id(service: str) -> str:
    return compose("ps", "-q", service).stdout.strip()


def crash(service: str) -> None:
    """A crash with no goodbye (SIGKILL). The restart policy is switched off first, otherwise
    Docker would bring the node back within seconds and hide the outage being tested."""
    cid = container_id(service)
    docker("update", "--restart=no", cid)
    docker("kill", cid)


def restore_cluster() -> None:
    """Back to 3 synced nodes, 3 healthy backends, network connected."""
    for service in (*NODES, "backend1", "backend2", "backend3"):
        docker("update", "--restart=unless-stopped", container_id(service))
    for service in (*NODES, "backend1", "backend2", "backend3"):
        compose("start", service)
    for node in NODES:  # the isolation test disconnects a node from the db network
        docker("network", "connect", f"{PROJECT}_db", container_id(node))
    wait_for(lambda: all(synced(n) for n in NODES), 180, "3 synced database nodes", 2)
    wait_for(lambda: cluster_size() == 3, 60, "cluster size 3")
    wait_for(
        lambda: httpx.get(f"{URL}/health", verify=False, timeout=30).status_code == 200, 90, "nginx health"
    )


def clear_reservations() -> None:
    for table in ("notice", "report", "stand_block", "removed_assignment", "reservation", "audit_log"):
        sql("galera1", f"DELETE FROM pistas.{table}")


@pytest.fixture(autouse=True)
def clean_cluster():
    restore_cluster()
    clear_reservations()
    yield
    restore_cluster()


class Client:
    def __init__(self, username: str):
        self.http = httpx.Client(base_url=URL, verify=False, timeout=30)
        for _ in range(6):  # nginx limits logins; wait out a spent budget instead of failing
            r = self.http.post(
                "/api/auth/login", json={"username": username, "password": SETTINGS.seed_password}
            )
            if r.status_code != 429:
                break
            time.sleep(15)
        assert r.status_code == 200, r.text
        self.http.headers["Authorization"] = f"Bearer {r.json()['token']}"


@pytest.fixture(scope="session")
def cluster_ready() -> None:
    """Whatever state an earlier run left behind, start from a healthy cluster before logging in."""
    restore_cluster()


@pytest.fixture(scope="session")
def tap(cluster_ready) -> Client:
    return Client("tap")


@pytest.fixture(scope="session")
def ana(cluster_ready) -> Client:
    return Client("ana")


def payload(i: int, *, request_id: str | None = None, stand: str | None = None, hours: int = 0) -> dict:
    """The i-th request. Distinct stand and day per i, so requests never compete with each other."""
    start = DAY + timedelta(days=i // len(STANDS), hours=hours)
    return {
        "requestId": request_id or str(uuid.uuid4()),
        "standId": stand or STANDS[i % len(STANDS)],
        "flightNumber": f"FT{i:05d}",
        "aircraftType": "ATR72",
        "start": start.isoformat(),
        "end": (start + timedelta(hours=1)).isoformat(),
        "handler": None,
    }


def send_with_retry(client: Client, body: dict, tries: int = 8) -> httpx.Response:
    """What the frontend would do: resend the SAME request id when the answer is lost or 5xx."""
    last: httpx.Response | Exception | None = None
    for _ in range(tries):
        try:
            r = client.http.post("/api/reservations", json=body)
            if r.status_code < 500:
                return r
            last = r
        except httpx.TransportError as exc:
            last = exc
        time.sleep(0.5)
    raise AssertionError(f"request kept failing: {last!r}")

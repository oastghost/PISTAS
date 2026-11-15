"""Fault tests T1 to T8 from CLAUDE.md section 11, against the real Docker stack.

A database node "crash" is `docker kill` (no goodbye to the cluster). `docker stop` is a clean
shutdown: the node leaves the cluster in an orderly way and the others keep quorum, even down to
a single node. The difference matters and is reported in 04_Documentacao_Tecnica.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from .conftest import (
    NODES,
    PROJECT,
    URL,
    Client,
    cluster_size,
    compose,
    container_id,
    crash,
    docker,
    payload,
    scalar,
    send_with_retry,
    sql,
    synced,
    wait_for,
)


def count(node: str, table: str = "reservation") -> int:
    return int(scalar(node, f"SELECT COUNT(*) FROM pistas.{table}"))


def assert_no_overlaps(node: str = "galera1") -> None:
    """The rule itself, checked on the data and not through the application."""
    dup = scalar(
        node,
        "SELECT COUNT(*) FROM pistas.stand_block a JOIN pistas.stand_block b "
        "ON a.stand_id = b.stand_id AND a.id < b.id "
        "AND a.occupied_from < b.occupied_to AND b.occupied_from < a.occupied_to",
    )
    assert dup == "0", "two overlapping blocks on one stand"


def run_workers(client: Client, n: int, fault, fault_after_s: float = 1.0, retry: bool = False):
    """n sequential-ish requests from 4 threads while `fault()` fires after a moment."""
    results: list[httpx.Response | Exception] = [None] * n  # type: ignore[list-item]
    bodies = [payload(i) for i in range(n)]

    def work(i: int) -> None:
        try:
            results[i] = (
                send_with_retry(client, bodies[i])
                if retry
                else client.http.post("/api/reservations", json=bodies[i])
            )
        except Exception as exc:  # noqa: BLE001 - recorded and judged by the test
            results[i] = exc

    timer = threading.Timer(fault_after_s, fault)
    timer.start()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(work, range(n)))
    timer.join()
    return bodies, results


def statuses(results) -> list:
    return [r.status_code if isinstance(r, httpx.Response) else repr(r) for r in results]


# T1: stop one database node during reservations. No visible errors, no duplicates.
def test_t1_database_node_crash_during_reservations(tap):
    bodies, results = run_workers(tap, 60, lambda: crash("galera2"))
    codes = statuses(results)
    assert codes.count(201) == 60, codes
    assert count("galera1") == 60
    assert_no_overlaps()
    assert cluster_size("galera1") == 2


# T2: stop one backend during a request. The retried request works and creates one reservation.
def test_t2_backend_stops_during_requests(tap):
    bodies, results = run_workers(
        tap, 60, lambda: docker("stop", "-t", "0", container_id("backend1")), retry=True
    )
    codes = statuses(results)
    assert codes.count(201) == 60, codes
    assert count("galera1") == 60
    assert len({b["requestId"] for b in bodies}) == 60


# T3: 20 simultaneous requests, same stand and time, through nginx and all 3 backends: exactly 1.
def test_t3_twenty_simultaneous_requests_exactly_one_approved(tap):
    def go(i: int) -> int:
        body = payload(0, stand="114")
        body["flightNumber"] = f"TP9{i:03d}"
        body["registration"] = f"CS-R{i:03d}"
        return tap.http.post("/api/reservations", json=body).status_code

    with ThreadPoolExecutor(max_workers=20) as pool:
        codes = list(pool.map(go, range(20)))
    assert codes.count(201) == 1, codes
    assert set(codes) <= {201, 409, 503}, codes
    assert count("galera1") == 1
    for node in NODES:
        assert scalar(node, "SELECT COUNT(*) FROM pistas.stand_block WHERE stand_id = '114'") == "1"
    print("T3 status codes:", sorted(codes))


# T4: the same request id twice. One reservation. Also sent at the same time to all backends.
def test_t4_same_request_id_creates_one_reservation(tap):
    body = payload(0, request_id=str(uuid.uuid4()))
    first = tap.http.post("/api/reservations", json=body)
    second = tap.http.post("/api/reservations", json=body)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] == second.json()["id"]

    body2 = payload(1, request_id=str(uuid.uuid4()))
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: tap.http.post("/api/reservations", json=body2), range(12)))
    assert {r.status_code for r in results} == {201}
    assert len({r.json()["id"] for r in results}) == 1
    assert count("galera1") == 2


# T5: isolate one database node from the network. It refuses writes, the others continue.
def test_t5_isolated_node_refuses_writes_others_continue(tap):
    docker("network", "disconnect", f"{PROJECT}_db", container_id("galera3"))
    wait_for(
        lambda: scalar("galera3", "SHOW STATUS LIKE 'wsrep_cluster_status'").endswith("non-Primary"),
        60,
        "isolated node to leave the primary component",
    )

    code, err = sql("galera3", "INSERT INTO pistas.audit_log (action) VALUES ('isolated-write')")
    assert code != 0 and "1047" in err, err  # WSREP has not yet prepared node for application use

    for i in range(10):
        r = tap.http.post("/api/reservations", json=payload(i))
        assert r.status_code == 201, r.text
    assert count("galera1") == 10
    assert cluster_size("galera1") == 2
    assert_no_overlaps()


# T6: two database nodes crash. No quorum: writes are refused cleanly and nothing is written.
def test_t6_two_nodes_down_writes_refused(tap):
    assert tap.http.post("/api/reservations", json=payload(0)).status_code == 201
    crash("galera2")
    crash("galera3")
    wait_for(
        lambda: scalar("galera1", "SHOW STATUS LIKE 'wsrep_cluster_status'").endswith("non-Primary"),
        60,
        "remaining node to lose the primary component",
    )

    codes = [tap.http.post("/api/reservations", json=payload(i)).status_code for i in range(1, 6)]
    assert set(codes) == {503}, codes
    assert httpx.get(f"{URL}/health", verify=False, timeout=60).status_code == 503

    for service in ("galera2", "galera3"):
        compose("start", service)
    wait_for(lambda: cluster_size("galera1") == 3, 180, "cluster back to 3 nodes", 2)
    assert count("galera1") == 1, "a refused request must not leave anything behind"
    assert tap.http.post("/api/reservations", json=payload(1)).status_code == 201


# T7: restart a stopped node. It syncs and rejoins with the same data as the others.
def test_t7_restarted_node_syncs_and_rejoins(tap):
    crash("galera2")
    wait_for(lambda: cluster_size("galera1") == 2, 60, "cluster to notice the missing node")
    for i in range(15):
        assert tap.http.post("/api/reservations", json=payload(i)).status_code == 201

    compose("start", "galera2")
    wait_for(lambda: cluster_size("galera1") == 3 and synced("galera2"), 180, "galera2 to rejoin", 2)
    assert count("galera2") == 15
    assert count("galera1") == count("galera2") == count("galera3") == 15
    assert_no_overlaps("galera2")


# T8: ANA removes an allocation with one node down. Removal and notice are saved together.
def test_t8_ana_removal_with_a_node_down(tap, ana):
    res = tap.http.post("/api/reservations", json=payload(0, stand="114")).json()
    crash("galera2")
    wait_for(lambda: cluster_size("galera1") == 2, 60, "cluster to notice the missing node")

    assert ana.http.delete(f"/api/reservations/{res['id']}").status_code == 204

    def state(node: str) -> tuple[str, str, str]:
        return (
            scalar(node, f"SELECT status FROM pistas.reservation WHERE id = '{res['id']}'"),
            scalar(node, f"SELECT COUNT(*) FROM pistas.notice WHERE reservation_id = '{res['id']}'"),
            scalar(node, f"SELECT COUNT(*) FROM pistas.stand_block WHERE reservation_id = '{res['id']}'"),
        )

    assert state("galera1") == ("removed", "1", "0")
    assert state("galera3") == ("removed", "1", "0")

    compose("start", "galera2")
    wait_for(lambda: cluster_size("galera1") == 3 and synced("galera2"), 180, "galera2 to rejoin", 2)
    assert state("galera2") == ("removed", "1", "0")
    notices = tap.http.get("/api/notices").json()
    assert len(notices) == 1 and "114" in notices[0]["message"]


# Extra: the login rate limit at nginx (CLAUDE.md section 7).
def test_login_is_rate_limited_by_nginx():
    c = httpx.Client(base_url=URL, verify=False, timeout=10)
    codes = [
        c.post("/api/auth/login", json={"username": "nobody", "password": "x"}).status_code for _ in range(25)
    ]
    assert 429 in codes, codes
    assert codes[0] == 401


# Extra: a clean stop (not a crash) of two nodes keeps the service up on the last node.
def test_clean_shutdown_of_two_nodes_keeps_service(tap):
    compose("stop", "galera2")
    compose("stop", "galera3")
    wait_for(lambda: cluster_size("galera1") == 1, 60, "cluster of one")
    r = tap.http.post("/api/reservations", json=payload(0))
    assert r.status_code == 201, r.text

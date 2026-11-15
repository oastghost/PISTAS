"""Airlines, dispatcher accounts and the ana_supervisor role."""

import itertools
import uuid
from datetime import timedelta

import httpx

from tests.conftest import Client

H = timedelta(hours=1)
PASSWORD = "a-long-temporary-password"


_prefix_counter = itertools.count()


def _new_airline(sup: Client, name: str, *prefixes: str) -> list[str]:
    """Creates an airline with prefixes of its own (a fresh one unless given) and returns them."""
    prefixes = prefixes or (f"Y{next(_prefix_counter):02d}",)
    r = sup.http.post("/api/admin/airlines", json={"name": name, "prefixes": list(prefixes)})
    assert r.status_code == 201, r.text
    return list(prefixes)


def _new_dispatcher(sup: Client, server: str, airline: str, username: str | None = None) -> dict:
    username = username or f"d{uuid.uuid4().hex[:8]}"
    r = sup.http.post(
        "/api/admin/users",
        json={
            "username": username,
            "name": f"Despachante {airline}",
            "email": f"{username}@pistas.test",
            "role": "despachante",
            "company": airline,
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


FINAL = "my-own-final-password-9"


def _raw_login(server: str, username: str, password: str) -> httpx.Response:
    return httpx.post(f"{server}/api/auth/login", json={"username": username, "password": password})


def _login(server: str, username: str, password: str = PASSWORD) -> httpx.Client:
    """Logs in and, for an account with a temporary password, completes the first-login change
    (to FINAL), so the returned client can use the whole API."""
    r = _raw_login(server, username, password)
    assert r.status_code == 200, r.text
    http = httpx.Client(base_url=server, timeout=30)
    http.headers["Authorization"] = f"Bearer {r.json()['token']}"
    if r.json()["user"]["mustChangePassword"]:
        done = http.post(
            "/api/auth/change-password", json={"currentPassword": password, "newPassword": FINAL}
        )
        assert done.status_code == 200, done.text
    return http


def test_only_the_supervisor_can_manage_accounts(login):
    for who in ("tap", "ana", "atc", "menzies"):
        c = login(who)
        assert c.http.get("/api/admin/users").status_code == 403, who
        assert (
            c.http.post("/api/admin/airlines", json={"name": "X Air", "prefixes": ["XA"]}).status_code == 403
        ), who
    assert login("supervisor").http.get("/api/admin/users").status_code == 200


def test_new_airline_and_two_dispatchers_share_the_airline(login, server, day):
    sup = login("supervisor")
    name = f"Air {uuid.uuid4().hex[:6]}"
    (prefix,) = _new_airline(sup, name)
    again = {"name": name, "prefixes": ["QQ" + prefix[-1]]}
    assert sup.http.post("/api/admin/airlines", json=again).status_code == 409

    a, b = _new_dispatcher(sup, server, name), _new_dispatcher(sup, server, name)
    http_a, http_b = _login(server, a["username"]), _login(server, b["username"])

    bid = http_a.post(
        "/api/reservations",
        json={
            "requestId": str(uuid.uuid4()),
            "standId": "114",
            "registration": "CS-ABC",
            "flightNumber": f"{prefix}100",
            "origin": "LEMD",
            "aircraftType": "A320",
            "start": (day + 8 * H).isoformat(),
            "end": (day + 10 * H).isoformat(),
            "handler": None,
        },
    )
    assert bid.status_code == 201, bid.text
    assert bid.json()["company"] == name

    # The request shows who made it, and the colleague sees it as the airline's own flight.
    listed = http_b.get("/api/reservations").json()
    mine = [r for r in listed if r["flightNumber"] == f"{prefix}100"][0]
    assert mine["company"] == name and mine["requestedBy"] == a["name"]

    # ANA removes it: BOTH dispatchers of the airline get the notice, other airlines do not.
    assert login("ana").http.delete(f"/api/reservations/{bid.json()['id']}").status_code == 204
    assert len(http_a.get("/api/notices").json()) == 1
    assert len(http_b.get("/api/notices").json()) == 1
    assert login("tap").http.get("/api/notices").json() == []


def test_dispatcher_cannot_bid_for_another_airline_request_id(login, server, day):
    sup = login("supervisor")
    tap = login("tap")
    rid = str(uuid.uuid4())
    assert tap.bid("114", start=day + 8 * H, request_id=rid).status_code == 201
    other = _new_dispatcher(sup, server, "easyJet")
    http = _login(server, other["username"])
    r = http.post(
        "/api/reservations",
        json={
            "requestId": rid,
            "standId": "115",
            "registration": "G-UZHA",
            "flightNumber": "U2100",
            "origin": "EGKK",
            "aircraftType": "A320",
            "start": (day + 8 * H).isoformat(),
            "end": (day + 10 * H).isoformat(),
            "handler": None,
        },
    )
    assert r.status_code == 400


def test_account_validation(login, server):
    sup = login("supervisor")
    base = {"name": "Teste", "email": "t@pistas.test", "role": "despachante", "company": "TAP"}
    post = lambda **kw: sup.http.post("/api/admin/users", json={**base, "password": PASSWORD, **kw})  # noqa: E731

    assert post(username="x" + uuid.uuid4().hex[:6], password="short").status_code == 400
    assert post(username="bad name!").status_code == 400
    assert post(username="x" + uuid.uuid4().hex[:6], company="No Such Air").status_code == 400
    assert post(username="x" + uuid.uuid4().hex[:6], company=None).status_code == 400
    assert post(username="x" + uuid.uuid4().hex[:6], role="ana").status_code == 400  # ana has no airline
    assert post(username="x" + uuid.uuid4().hex[:6], role="controlador", company=None).status_code == 400
    assert post(username="tap").status_code == 409  # taken


def test_disabled_account_is_locked_out_at_once_and_can_come_back(login, server):
    sup = login("supervisor")
    acc = _new_dispatcher(sup, server, "TAP")
    http = _login(server, acc["username"])
    assert http.get("/api/auth/me").status_code == 200

    assert sup.http.patch(f"/api/admin/users/{acc['id']}", json={"active": False}).status_code == 200
    assert http.get("/api/auth/me").status_code == 401  # the old token stops working
    r = httpx.post(f"{server}/api/auth/login", json={"username": acc["username"], "password": FINAL})
    assert r.status_code == 401

    assert sup.http.patch(f"/api/admin/users/{acc['id']}", json={"active": True}).status_code == 200
    _login(server, acc["username"], FINAL)


def test_password_reset(login, server):
    sup = login("supervisor")
    acc = _new_dispatcher(sup, server, "TAP")
    new = "another-long-password-42"
    assert sup.http.patch(f"/api/admin/users/{acc['id']}", json={"password": "short"}).status_code == 400
    assert sup.http.patch(f"/api/admin/users/{acc['id']}", json={"password": new}).status_code == 200
    assert (
        httpx.post(
            f"{server}/api/auth/login", json={"username": acc["username"], "password": PASSWORD}
        ).status_code
        == 401
    )
    _login(server, acc["username"], new)


def test_supervisor_cannot_touch_itself_or_other_roles(login):
    sup = login("supervisor")
    users = {u["username"]: u for u in sup.http.get("/api/admin/users").json()}
    assert (
        sup.http.patch(f"/api/admin/users/{users['supervisor']['id']}", json={"active": False}).status_code
        == 404
    )
    assert sup.http.patch(f"/api/admin/users/{users['atc']['id']}", json={"active": False}).status_code == 404
    assert (
        sup.http.patch(f"/api/admin/users/{users['menzies']['id']}", json={"active": False}).status_code
        == 404
    )


def test_supervisor_oversees_everything_an_ana_operator_does(login, day):
    tap, atc, sup = login("tap"), login("atc"), login("supervisor")
    res = tap.bid("114", start=day + 8 * H).json()
    assert atc.http.post("/api/reports", json={"reservationId": res["id"], "text": "x"}).status_code == 201
    assert [r["text"] for r in sup.http.get("/api/reports").json()] == ["x"]
    assert sup.http.delete(f"/api/reservations/{res['id']}").status_code == 204
    # but a supervisor does not make reservations
    assert sup.bid("115", start=day + 8 * H).status_code == 403


def test_changes_are_audited(login, server):
    sup = login("supervisor")
    name = f"Audit {uuid.uuid4().hex[:6]}"
    (prefix,) = _new_airline(sup, name)
    acc = _new_dispatcher(sup, server, name)
    sup.http.patch(f"/api/admin/users/{acc['id']}", json={"active": False})
    log = sup.http.get("/api/admin/audit").json()
    actions = [(e["action"], e["detail"]) for e in log if e["username"] == "supervisor"]
    assert ("airline_created", f"{name} ({prefix})") in actions
    assert ("user_disabled", acc["username"]) in actions
    assert any(a == "user_created" and acc["username"] in d for a, d in actions)


def test_airline_list_counts_dispatchers(login, server):
    sup = login("supervisor")
    name = f"Count {uuid.uuid4().hex[:6]}"
    _new_airline(sup, name)
    a, _b = _new_dispatcher(sup, server, name), _new_dispatcher(sup, server, name)
    sup.http.patch(f"/api/admin/users/{a['id']}", json={"active": False})
    row = [x for x in sup.http.get("/api/admin/airlines").json() if x["name"] == name][0]
    assert (row["dispatchers"], row["activeDispatchers"]) == (2, 1)

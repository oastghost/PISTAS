"""Each airline's flight numbers must start with one of its own prefixes."""

import uuid
from datetime import timedelta

from app.db import connect
from tests.conftest import registration_for
from tests.test_accounts import _login, _new_airline, _new_dispatcher

H = timedelta(hours=1)


def _bid(http, flight: str, day, *, stand: str = "114"):
    return http.post(
        "/api/reservations",
        json={
            "requestId": str(uuid.uuid4()),
            "standId": stand,
            "registration": registration_for(flight),
            "flightNumber": flight,
            "origin": "LEMD",
            "aircraftType": "A320",
            "start": (day + 8 * H).isoformat(),
            "end": (day + 10 * H).isoformat(),
            "handler": None,
        },
    )


def test_flight_must_start_with_the_airline_prefix(login, day):
    tap, easyjet = login("tap"), login("easyjet")
    ok = ["TAP123", "TP1", "TP1234", "TP123A", "tp77"]
    for i, flight in enumerate(ok):
        r = tap.bid("114", start=day + (2 * i) * H, hours=1, flight=flight)
        assert r.status_code == 201, (flight, r.text)
    assert tap.bid("114", start=day + 20 * H, flight="TP77").json()["flightNumber"] == "TP77"

    for bad in ["EZY123", "U2100", "RYR1", "TPX1", "TP12345", "TP", "TAP", "XTP123", "TP12AB", "T P1"]:
        r = tap.bid("115", start=day + 8 * H, flight=bad)
        assert r.status_code == 400, (bad, r.text)

    # and the other way round: easyJet cannot use TAP's prefixes
    assert easyjet.bid("116", start=day + 8 * H, flight="TP100").status_code == 400
    assert easyjet.bid("116", start=day + 8 * H, flight="EZY100").status_code == 201
    assert easyjet.bid("117", start=day + 8 * H, flight="U2100").status_code == 201


def test_error_message_names_the_prefixes(login, day):
    r = login("tap").bid("114", start=day + 8 * H, flight="RYR1")
    assert r.status_code == 400
    assert "TAP" in r.json()["message"] and "TP" in r.json()["message"]


def test_new_airline_gets_its_own_prefix_and_nobody_else_can_use_it(login, server, day):
    sup = login("supervisor")
    name = f"Ryan {uuid.uuid4().hex[:5]}"
    r = sup.http.post("/api/admin/airlines", json={"name": name, "prefixes": ["ryr", " fr "]})
    assert r.status_code == 201 and r.json()["prefixes"] == ["FR", "RYR"]

    acc = _new_dispatcher(sup, server, name)
    ryan = _login(server, acc["username"])
    assert ryan.get("/api/auth/me").json()["flightPrefixes"] == ["FR", "RYR"]
    assert _bid(ryan, "RYR1234", day).status_code == 201
    assert _bid(ryan, "FR12", day, stand="115").status_code == 201
    assert _bid(ryan, "TP123", day, stand="116").status_code == 400
    assert login("tap").bid("117", start=day + 8 * H, flight="RYR9").status_code == 400


def test_prefix_belongs_to_one_airline(login):
    sup = login("supervisor")
    n = uuid.uuid4().hex[:5]
    r = sup.http.post("/api/admin/airlines", json={"name": f"Thief {n}", "prefixes": ["TAP"]})
    assert r.status_code == 409 and "TAP" in r.json()["message"]
    # nothing was half-created
    assert f"Thief {n}" not in [a["name"] for a in sup.http.get("/api/admin/airlines").json()]


def test_prefix_format_is_validated(login):
    sup = login("supervisor")
    for bad in (["R"], ["RYRX"], ["R-R"], [], ["AA", "BB", "CC", "DD", "EE", "FF", "GG"]):
        r = sup.http.post(
            "/api/admin/airlines", json={"name": f"Bad {uuid.uuid4().hex[:5]}", "prefixes": bad}
        )
        assert r.status_code == 400, bad


def test_airline_without_prefix_cannot_request_until_it_has_one(login, server, day):
    sup = login("supervisor")
    name = f"Legacy {uuid.uuid4().hex[:5]}"
    conn = connect(autocommit=True)  # an airline created before prefixes existed
    with conn.cursor() as cur:
        cur.execute("INSERT INTO airline (name) VALUES (%s)", (name,))
    conn.close()
    acc = _new_dispatcher(sup, server, name)
    http = _login(server, acc["username"])

    r = _bid(http, "LGC100", day)
    assert r.status_code == 400 and "prefixo" in r.json()["message"]

    added = sup.http.post(f"/api/admin/airlines/{name}/prefixes", json={"prefix": "lgc"})
    assert added.status_code == 201 and added.json()["prefixes"] == ["LGC"]
    assert _bid(http, "LGC100", day).status_code == 201


def test_add_and_remove_prefixes(login):
    sup = login("supervisor")
    name = f"Edit {uuid.uuid4().hex[:5]}"
    (first,) = _new_airline(sup, name)
    second = "E" + first[1:]
    assert sup.http.post(f"/api/admin/airlines/{name}/prefixes", json={"prefix": second}).status_code == 201
    assert sup.http.post(f"/api/admin/airlines/{name}/prefixes", json={"prefix": "TP"}).status_code == 409
    assert sup.http.post("/api/admin/airlines/Nope/prefixes", json={"prefix": "NN"}).status_code == 404

    r = sup.http.delete(f"/api/admin/airlines/{name}/prefixes/{second}")
    assert r.status_code == 200 and r.json()["prefixes"] == [first]
    assert sup.http.delete(f"/api/admin/airlines/{name}/prefixes/{first}").status_code == 400  # the last one
    assert sup.http.delete(f"/api/admin/airlines/{name}/prefixes/{second}").status_code == 404

    log = sup.http.get("/api/admin/audit").json()
    details = {(e["action"], e["detail"]) for e in log}
    assert ("prefix_added", f"{name}: {second}") in details
    assert ("prefix_removed", f"{name}: {second}") in details


def test_only_the_supervisor_changes_prefixes(login):
    for who in ("tap", "ana", "atc"):
        c = login(who)
        assert c.http.post("/api/admin/airlines/TAP/prefixes", json={"prefix": "ZZ"}).status_code == 403
        assert c.http.delete("/api/admin/airlines/TAP/prefixes/TP").status_code == 403


def test_non_dispatchers_have_no_prefixes(login):
    assert login("ana").http.get("/api/auth/me").json()["flightPrefixes"] == []
    assert login("tap").http.get("/api/auth/me").json()["flightPrefixes"] == ["TAP", "TP"]

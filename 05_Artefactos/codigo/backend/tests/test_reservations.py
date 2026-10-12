"""Behaviour of the reservation rules and the roles."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pymysql

from app.db import connect

H = timedelta(hours=1)


def _count(sql: str, *args) -> int:
    conn = connect(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchone().values())[0]
    finally:
        conn.close()


# T3: 20 simultaneous requests for the same stand and time, exactly 1 approved.
def test_t3_twenty_simultaneous_bids_one_wins(login, day):
    tap, easyjet = login("tap"), login("easyjet")
    clients = [tap, easyjet] * 10

    def go(i: int) -> int:
        return clients[i].bid("114", start=day + 8 * H, flight=f"XX{i:03d}").status_code

    with ThreadPoolExecutor(max_workers=20) as pool:
        codes = list(pool.map(go, range(20)))

    assert codes.count(201) == 1, codes
    assert codes.count(409) == 19, codes
    assert _count("SELECT COUNT(*) FROM reservation WHERE stand_id = '114'") == 1
    assert _count("SELECT COUNT(*) FROM stand_block WHERE stand_id = '114'") == 1


# T4: the same request id sent twice creates one reservation and returns the first result.
def test_t4_same_request_id_twice_one_reservation(login, day):
    tap = login("tap")
    rid = str(uuid.uuid4())
    first = tap.bid("114", start=day + 8 * H, request_id=rid)
    second = tap.bid("114", start=day + 8 * H, request_id=rid)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert _count("SELECT COUNT(*) FROM reservation") == 1


def test_t4_same_request_id_sent_concurrently(login, day):
    tap = login("tap")
    rid = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: tap.bid("114", start=day + 8 * H, request_id=rid), range(10)))
    assert {r.status_code for r in results} == {201}
    assert len({r.json()["id"] for r in results}) == 1
    assert _count("SELECT COUNT(*) FROM reservation") == 1


def test_overlap_refused_adjacent_after_gap_accepted(login, day):
    tap = login("tap")
    assert tap.bid("114", start=day + 8 * H, hours=2).status_code == 201  # 08:00-10:00
    assert tap.bid("114", start=day + 9 * H, hours=2).status_code == 409  # overlaps
    assert tap.bid("114", start=day + 10 * H, hours=1).status_code == 409  # inside 30 min gap
    assert tap.bid("114", start=day + 10 * H + timedelta(minutes=30)).status_code == 201
    assert tap.bid("115", start=day + 8 * H).status_code == 201  # other stand


def test_database_rejects_overlap_even_if_python_checks_are_bypassed(login, day):
    tap = login("tap")
    rid = tap.bid("114", start=day + 8 * H).json()["id"]
    conn = connect(autocommit=True)
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO stand_block (reservation_id, stand_id, occupied_from, occupied_to) "
                    "VALUES (%s, '114', '2030-06-15 09:00:00', '2030-06-15 11:00:00')",
                    (rid,),
                )
                raise AssertionError("overlapping block was accepted")
            except pymysql.IntegrityError as exc:
                assert exc.args[0] == 1062
    finally:
        conn.close()


def test_aircraft_must_fit_the_stand(login, day):
    tap = login("tap")
    resp = tap.bid("108", start=day + 8 * H, aircraft="A320")  # stand 108 is ATR72 only
    assert resp.status_code == 409
    assert resp.json()["code"] == "STAND_TOO_SMALL"
    assert tap.bid("108", start=day + 8 * H, aircraft="ATR72").status_code == 201


def test_suggestions_are_free_compatible_and_exclude_the_wanted_stand(login, day):
    tap = login("tap")
    assert tap.bid("114", start=day + 8 * H).status_code == 201
    resp = tap.http.post(
        "/api/reservations/suggestions",
        json={
            "requestId": str(uuid.uuid4()),
            "standId": "114",
            "flightNumber": "TP2",
            "aircraftType": "A320",
            "start": (day + 8 * H).isoformat(),
            "end": (day + 10 * H).isoformat(),
            "handler": None,
        },
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert ids and "114" not in ids and len(ids) <= 5
    assert ids[0] in {"115", "116", "117"}  # same apron first


def test_ana_removal_writes_notice_and_frees_the_stand_in_one_step(login, day):
    tap, ana = login("tap"), login("ana")
    res = tap.bid("114", start=day + 8 * H, flight="TP5", handler="Menzies").json()

    assert ana.http.delete(f"/api/reservations/{res['id']}").status_code == 204

    notices = tap.http.get("/api/notices").json()
    assert len(notices) == 1
    assert "TP5" in notices[0]["message"] and "+351 000 000 000 (teste)" in notices[0]["message"]
    assert _count("SELECT COUNT(*) FROM stand_block WHERE stand_id = '114'") == 0
    assert _count("SELECT COUNT(*) FROM audit_log WHERE action = 'ana_removal'") == 1
    # The stand is free for someone else, but the flight cannot return to it.
    assert login("easyjet").bid("114", start=day + 8 * H, flight="U2").status_code == 201
    again = tap.bid("114", start=day + 12 * H, flight="TP5")
    assert again.status_code == 409 and again.json()["code"] == "STAND_UNAVAILABLE"


def test_removing_twice_is_not_found(login, day):
    tap, ana = login("tap"), login("ana")
    res = tap.bid("114", start=day + 8 * H).json()
    assert ana.http.delete(f"/api/reservations/{res['id']}").status_code == 204
    assert ana.http.delete(f"/api/reservations/{res['id']}").status_code == 404


def test_roles_are_enforced_by_the_backend(login, day):
    tap, ana, atc, menzies = login("tap"), login("ana"), login("atc"), login("menzies")
    res = tap.bid("114", start=day + 8 * H, handler="Menzies").json()

    assert ana.bid("115", start=day + 8 * H).status_code == 403  # ANA cannot reserve
    assert atc.bid("115", start=day + 8 * H).status_code == 403  # controller cannot
    assert menzies.bid("115", start=day + 8 * H).status_code == 403  # handler cannot
    assert tap.http.delete(f"/api/reservations/{res['id']}").status_code == 403
    assert atc.http.delete(f"/api/reservations/{res['id']}").status_code == 403
    assert menzies.http.delete(f"/api/reservations/{res['id']}").status_code == 403
    assert tap.http.post("/api/reports", json={"reservationId": res["id"], "text": "x"}).status_code == 403
    assert ana.http.get("/api/notices").status_code == 403


def test_controller_report_reaches_ana(login, day):
    tap, atc, ana = login("tap"), login("atc"), login("ana")
    res = tap.bid("114", start=day + 8 * H).json()
    created = atc.http.post("/api/reports", json={"reservationId": res["id"], "text": "Obstrução"})
    assert created.status_code == 201
    reports = ana.http.get("/api/reports").json()
    assert [r["text"] for r in reports] == ["Obstrução"]
    assert login("tap").http.get("/api/reports").status_code == 403


def test_handler_only_sees_its_own_requests(login, day):
    tap, menzies = login("tap"), login("menzies")
    tap.bid("114", start=day + 8 * H, flight="TP1", handler="Menzies")
    tap.bid("115", start=day + 8 * H, flight="TP2", handler="Portway")
    tap.bid("116", start=day + 8 * H, flight="TP3")
    seen = menzies.http.get("/api/reservations").json()
    assert [r["flightNumber"] for r in seen] == ["TP1"]
    assert len(tap.http.get("/api/reservations").json()) == 3


def test_authentication_required_and_login_rules(server, login):
    import httpx

    anon = httpx.Client(base_url=server)
    assert anon.get("/api/reservations").status_code == 401
    assert anon.get("/health").status_code == 200
    bad = anon.post("/api/auth/login", json={"username": "tap", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["code"] == "INVALID_CREDENTIALS"
    assert _count("SELECT COUNT(*) FROM audit_log WHERE action = 'login_failed'") == 1
    login("tap")
    assert _count("SELECT COUNT(*) FROM audit_log WHERE action = 'login'") == 1
    forged = httpx.Client(base_url=server, headers={"Authorization": "Bearer not.a.token"})
    assert forged.get("/api/reservations").status_code == 401


def test_input_is_validated(login, day):
    tap = login("tap")
    assert tap.bid("999", start=day + 8 * H).status_code == 400  # unknown stand
    assert tap.bid("114", start=day + 8 * H, aircraft="XXXX").status_code == 400  # unknown type
    assert tap.bid("114", start=day + 8 * H, flight="bad flight!").status_code == 400
    assert tap.bid("114", start=day + 8 * H, hours=-1).status_code == 400
    assert tap.bid("114", start=day + 8 * H, handler="Nobody").status_code == 400
    assert tap.bid("114", start=day + 8 * H, request_id="not-a-uuid").status_code == 400
    assert _count("SELECT COUNT(*) FROM reservation") == 0

"""A temporary password must be replaced at the first login, and the backend enforces it."""

import uuid

import httpx

from tests.test_accounts import FINAL, PASSWORD, _new_dispatcher, _raw_login

TEMP_ALLOWED = ("/api/auth/me",)


def _fresh(login, server) -> tuple[httpx.Client, dict]:
    sup = login("supervisor")
    acc = _new_dispatcher(sup, server, "TAP")
    r = _raw_login(server, acc["username"], PASSWORD)
    assert r.status_code == 200
    assert r.json()["user"]["mustChangePassword"] is True
    http = httpx.Client(base_url=server, timeout=30)
    http.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return http, acc


def test_new_account_is_locked_to_the_password_change(login, server):
    http, _ = _fresh(login, server)
    me = http.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["mustChangePassword"] is True
    for path in ("/api/reservations", "/api/stands", "/api/notices", "/api/aircraft-types"):
        r = http.get(path)
        assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED", path
    assert http.post("/api/reservations/suggestions", json={}).status_code in (400, 403)


def test_changing_the_password_unlocks_the_account(login, server):
    http, acc = _fresh(login, server)
    r = http.post("/api/auth/change-password", json={"currentPassword": PASSWORD, "newPassword": FINAL})
    assert r.status_code == 200 and r.json()["mustChangePassword"] is False
    assert http.get("/api/stands").status_code == 200  # same token, now unlocked
    assert _raw_login(server, acc["username"], PASSWORD).status_code == 401
    again = _raw_login(server, acc["username"], FINAL)
    assert again.status_code == 200 and again.json()["user"]["mustChangePassword"] is False


def test_change_is_refused_with_wrong_current_weak_or_same_password(login, server):
    http, _ = _fresh(login, server)

    def change(cur: str, new: str) -> httpx.Response:
        return http.post("/api/auth/change-password", json={"currentPassword": cur, "newPassword": new})

    assert change("not-the-password", FINAL).status_code == 401  # a stolen token is not enough
    assert change(PASSWORD, "short").status_code == 400
    assert change(PASSWORD, PASSWORD).status_code == 400
    assert http.get("/api/stands").status_code == 403  # still locked after the failures


def test_supervisor_reset_locks_the_account_again(login, server):
    http, acc = _fresh(login, server)
    http.post("/api/auth/change-password", json={"currentPassword": PASSWORD, "newPassword": FINAL})
    assert http.get("/api/stands").status_code == 200

    temp = "supervisor-set-temp-" + uuid.uuid4().hex[:6]
    sup = login("supervisor")
    assert sup.http.patch(f"/api/admin/users/{acc['id']}", json={"password": temp}).status_code == 200
    # the open session is locked at once, not only the next login
    assert http.get("/api/stands").status_code == 403
    r = _raw_login(server, acc["username"], temp)
    assert r.json()["user"]["mustChangePassword"] is True


def test_seeded_accounts_are_not_forced(login):
    for who in ("tap", "ana", "supervisor"):
        assert login(who).http.get("/api/auth/me").json()["mustChangePassword"] is False


def test_password_change_is_audited_without_the_password(login, server):
    http, acc = _fresh(login, server)
    http.post("/api/auth/change-password", json={"currentPassword": PASSWORD, "newPassword": FINAL})
    log = login("supervisor").http.get("/api/admin/audit").json()
    entry = [e for e in log if e["action"] == "password_changed" and e["username"] == acc["username"]]
    assert entry and FINAL not in str(log) and PASSWORD not in str(log)

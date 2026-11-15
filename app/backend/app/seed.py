"""Loads reference data (stands, aircraft types) and the staff accounts.

Accounts are created here only: there is no registration in the app. All seeded accounts get
the password from SEED_PASSWORD (.env), hashed with Argon2id. Safe to run again.
"""

import json
import sys

from .config import ROOT, get_settings
from .db import connect
from .security import hash_password

SEED_DIR = ROOT / "db" / "seed"

# username, display name, role, company, e-mail. Companies, handlers and addresses are simulated
# (.test is a reserved domain). Every account with role ana gets the report alerts.
ACCOUNTS = [
    ("tap", "Despachante TAP", "despachante", "TAP", "tap@pistas.test"),
    ("tap2", "Despachante TAP (turno 2)", "despachante", "TAP", "tap2@pistas.test"),
    ("easyjet", "Despachante easyJet", "despachante", "easyJet", "easyjet@pistas.test"),
    ("easyjet2", "Despachante easyJet (turno 2)", "despachante", "easyJet", "easyjet2@pistas.test"),
    ("supervisor", "Supervisão ANA", "ana_supervisor", None, "supervisor@pistas.test"),
    ("ana", "Operações ANA", "ana", None, "ana@pistas.test"),
    ("ana2", "Operações ANA (turno 2)", "ana", None, "ana2@pistas.test"),
    ("ana3", "Operações ANA (piquete)", "ana", None, "ana3@pistas.test"),
    ("atc", "Controlador de tráfego", "controlador", None, "atc@pistas.test"),
    ("menzies", "Menzies", "handler", "Menzies", "menzies@pistas.test"),
    ("portway", "Portway", "handler", "Portway", "portway@pistas.test"),
]


# Flight number prefixes of the simulated airlines. Real ones are added by the supervisor.
AIRLINE_PREFIXES = {"TAP": ["TAP", "TP"], "easyJet": ["EZY", "U2"]}


def seed(password: str, **connection_overrides) -> None:
    stands = json.loads((SEED_DIR / "stands.json").read_text(encoding="utf-8"))
    aircraft = json.loads((SEED_DIR / "aircraft_types.json").read_text(encoding="utf-8"))
    conn = connect(autocommit=False, **connection_overrides)
    try:
        with conn.cursor() as cur:
            for s in stands:
                cur.execute(
                    "INSERT INTO stand (id, name, apron, critical, category, max_wingspan_m) "
                    "VALUES (%(id)s, %(name)s, %(apron)s, %(critical)s, %(category)s, %(max_wingspan_m)s) "
                    "ON DUPLICATE KEY UPDATE name=VALUES(name), apron=VALUES(apron), "
                    "critical=VALUES(critical), category=VALUES(category), "
                    "max_wingspan_m=VALUES(max_wingspan_m)",
                    s,
                )
            for a in aircraft:
                cur.execute(
                    "INSERT INTO aircraft_type (code, label, category, wingspan_m) "
                    "VALUES (%(code)s, %(label)s, %(category)s, %(wingspan_m)s) "
                    "ON DUPLICATE KEY UPDATE label=VALUES(label), category=VALUES(category), "
                    "wingspan_m=VALUES(wingspan_m)",
                    a,
                )
            for airline in sorted({a[3] for a in ACCOUNTS if a[2] == "despachante"}):
                cur.execute("INSERT IGNORE INTO airline (name) VALUES (%s)", (airline,))
            for airline, prefixes in AIRLINE_PREFIXES.items():
                for prefix in prefixes:
                    cur.execute(
                        "INSERT IGNORE INTO airline_prefix (prefix, airline) VALUES (%s, %s)",
                        (prefix, airline),
                    )
            for username, name, role, company, email in ACCOUNTS:
                cur.execute(
                    "INSERT INTO app_user (username, password_hash, name, email, role, company) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), name=VALUES(name), "
                    "email=VALUES(email), role=VALUES(role), company=VALUES(company)",
                    (username, hash_password(password), name, email, role, company),
                )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    pw = get_settings().seed_password
    if not pw:
        sys.exit("Set SEED_PASSWORD in .env (see .env.example)")
    seed(pw)
    print(f"seeded {len(ACCOUNTS)} accounts, stands and aircraft types")

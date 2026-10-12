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

# username, display name, role, company. Companies and handlers are simulated.
ACCOUNTS = [
    ("tap", "Despachante TAP", "despachante", "TAP"),
    ("easyjet", "Despachante easyJet", "despachante", "easyJet"),
    ("ana", "Operações ANA", "ana", None),
    ("atc", "Controlador de tráfego", "controlador", None),
    ("menzies", "Menzies", "handler", "Menzies"),
    ("portway", "Portway", "handler", "Portway"),
]


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
            for username, name, role, company in ACCOUNTS:
                cur.execute(
                    "INSERT INTO app_user (username, password_hash, name, role, company) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), name=VALUES(name), "
                    "role=VALUES(role), company=VALUES(company)",
                    (username, hash_password(password), name, role, company),
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

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # .../app


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT / "backend" / ".env"), extra="ignore")

    db_host: str = "127.0.0.1"
    # Comma separated, preferred node first. Used instead of db_host when set (Galera).
    db_hosts: str = ""
    db_port: int = 3306
    db_name: str = "pistas"
    db_user: str = "pistas"
    db_password: str = ""
    db_root_password: str = ""  # tests and tooling only

    jwt_secret: str
    jwt_minutes: int = 30

    # Galera: make reads wait for the node to apply pending writes. 0 on a single node.
    wsrep_sync_wait: int = 0

    # Minutes added after departure before the stand is free again (provisional).
    turnaround_minutes: int = 30

    # Placeholder. The real number must come from ANA before delivery.
    ana_phone: str = "913 560 661"

    # E-mail alerts to ANA. Empty smtp_host switches them off (no outbox rows, no worker).
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "pistas@localhost"
    mail_max_attempts: int = 6
    mail_poll_seconds: float = 5.0

    cors_origins: str = "http://localhost:5173"

    # Password for the seeded staff accounts, see app/seed.py.
    seed_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

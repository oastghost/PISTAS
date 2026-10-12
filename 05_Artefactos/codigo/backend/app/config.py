from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # .../codigo


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT / "backend" / ".env"), extra="ignore")

    db_host: str = "127.0.0.1"
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
    ana_phone: str = "+351 000 000 000 (simulado)"

    cors_origins: str = "http://localhost:5173"

    # Password for the seeded staff accounts, see app/seed.py.
    seed_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

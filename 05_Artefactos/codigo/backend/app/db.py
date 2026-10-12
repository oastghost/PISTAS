from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from .config import get_settings

# MySQL/MariaDB error numbers the code reacts to.
DUPLICATE_KEY = 1062
DEADLOCK = 1213  # Galera certification failure shows up as a deadlock
LOCK_WAIT_TIMEOUT = 1205
RETRYABLE = (DEADLOCK, LOCK_WAIT_TIMEOUT)


def connect(database: str | None = None, **overrides) -> pymysql.Connection:
    s = get_settings()
    params = {
        "host": s.db_host,
        "port": s.db_port,
        "user": s.db_user,
        "password": s.db_password,
        "database": s.db_name if database is None else database,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
        "connect_timeout": 5,
    }
    params.update(overrides)
    conn = pymysql.connect(**params)
    if s.wsrep_sync_wait:
        with conn.cursor() as cur:
            cur.execute("SET SESSION wsrep_sync_wait = %s", (s.wsrep_sync_wait,))
    return conn


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """One connection, one transaction. Commits on success, rolls back on any exception."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def error_code(exc: pymysql.MySQLError) -> int:
    return exc.args[0] if exc.args and isinstance(exc.args[0], int) else 0

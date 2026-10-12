import time
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from .config import get_settings

# MySQL/MariaDB error numbers the code reacts to.
DUPLICATE_KEY = 1062
DEADLOCK = 1213  # Galera certification failure shows up as a deadlock
LOCK_WAIT_TIMEOUT = 1205
NOT_PRIMARY = 1047  # a Galera node without quorum refuses everything
CANNOT_CONNECT = 2003
SERVER_GONE = 2006
LOST_CONNECTION = 2013
# Repeating the whole transaction is safe for these: nothing was committed, or the request id
# makes the repeat idempotent.
RETRYABLE = (DEADLOCK, LOCK_WAIT_TIMEOUT, NOT_PRIMARY, CANNOT_CONNECT, SERVER_GONE, LOST_CONNECTION)

BAD_NODE_SECONDS = 5.0
_bad_until: dict[str, float] = {}


def _hosts() -> list[str]:
    s = get_settings()
    configured = [h.strip() for h in (s.db_hosts or s.db_host).split(",") if h.strip()]
    now = time.monotonic()
    healthy = [h for h in configured if _bad_until.get(h, 0.0) <= now]
    recently_bad = [h for h in configured if h not in healthy]
    return healthy + recently_bad


def _mark_bad(host: str) -> None:
    _bad_until[host] = time.monotonic() + BAD_NODE_SECONDS


def connect(database: str | None = None, **overrides) -> pymysql.Connection:
    """Connects to the first node that answers a query. A node that lost quorum accepts the
    connection but refuses every statement, so the probe is what tells it apart."""
    s = get_settings()
    params = {
        "port": s.db_port,
        "user": s.db_user,
        "password": s.db_password,
        "database": s.db_name if database is None else database,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
        "connect_timeout": 2,
        "read_timeout": 20,
        "write_timeout": 20,
    }
    params.update(overrides)
    last_error: Exception | None = None
    for host in _hosts():
        try:
            conn = pymysql.connect(host=host, **params)
        except pymysql.MySQLError as exc:
            _mark_bad(host)
            last_error = exc
            continue
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                if s.wsrep_sync_wait:
                    cur.execute("SET SESSION wsrep_sync_wait = %s", (s.wsrep_sync_wait,))
        except pymysql.MySQLError as exc:
            _mark_bad(host)
            last_error = exc
            conn.close()
            continue
        return conn
    assert last_error is not None
    raise last_error


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """One connection, one transaction. Commits on success, rolls back on any exception."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except BaseException as exc:
        try:
            conn.rollback()
        except pymysql.MySQLError:
            pass  # the connection is gone, the server rolled the transaction back
        if isinstance(exc, pymysql.MySQLError) and error_code(exc) in (
            NOT_PRIMARY,
            SERVER_GONE,
            LOST_CONNECTION,
        ):
            _mark_bad(conn.host)
        raise
    finally:
        conn.close()


def error_code(exc: pymysql.MySQLError) -> int:
    return exc.args[0] if exc.args and isinstance(exc.args[0], int) else 0

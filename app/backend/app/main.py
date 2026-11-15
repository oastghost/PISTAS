import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import notify
from .admin import router as admin_router
from .config import get_settings
from .db import transaction
from .errors import ApiError, api_error_handler, database_error_handler, validation_error_handler
from .routes import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    stop = threading.Event()
    if notify.enabled():
        threading.Thread(target=notify.run_worker, args=(stop,), name="mail-outbox", daemon=True).start()
    yield
    stop.set()


def create_app() -> FastAPI:
    app = FastAPI(title="A PISTAS", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(pymysql.MySQLError, database_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)
    app.include_router(admin_router)

    @app.get("/health")
    def health() -> JSONResponse:
        """No authentication, for the load balancer. Healthy only if the database answers."""
        try:
            with transaction() as cur:
                cur.execute("SELECT 1")
                # On Galera, only a node in the Primary component may take part.
                cur.execute("SELECT @@wsrep_on AS on_")
                if cur.fetchone()["on_"]:
                    cur.execute("SHOW GLOBAL STATUS LIKE 'wsrep_cluster_status'")
                    row = cur.fetchone()
                    if row is None or row["Value"] != "Primary":
                        raise RuntimeError("not in the primary component")
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ok"})

    return app


app = create_app()

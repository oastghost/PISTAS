from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import transaction
from .errors import ApiError, api_error_handler, validation_error_handler
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="A PISTAS", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> JSONResponse:
        """No authentication, for the load balancer. Healthy only if the database answers."""
        try:
            with transaction() as cur:
                cur.execute("SELECT 1")
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ok"})

    return app


app = create_app()

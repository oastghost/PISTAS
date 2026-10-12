from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Codes match ApiErrorCode in the frontend (src/api/client.ts).
STATUS = {
    "INVALID_CREDENTIALS": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "INVALID_INPUT": 400,
    "STAND_TOO_SMALL": 409,
    "STAND_UNAVAILABLE": 409,
    "UNAVAILABLE": 503,
}


class ApiError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS.get(exc.code, 400), content={"code": exc.code, "message": exc.message}
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400, content={"code": "INVALID_INPUT", "message": "Dados do pedido inválidos."}
    )

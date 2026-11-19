from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class StoreAPIError(Exception):
    """Expected, localized error raised by the store registration API."""

    def __init__(self, status_code: int, message: str, errors: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.errors = errors
        super().__init__(message)


async def store_api_error_handler(request: Request, exc: StoreAPIError) -> JSONResponse:
    body = {"success": False, "message": exc.message}
    if exc.errors:
        body["errors"] = exc.errors
    return JSONResponse(status_code=exc.status_code, content=body)


async def store_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if request.url.path.startswith("/api/stores"):
        message = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ."
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": message},
            headers=exc.headers,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": jsonable_encoder(exc.detail)},
        headers=exc.headers,
    )

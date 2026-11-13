"""Chuẩn hóa format response cho API RideHub."""
from typing import Any, Optional
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def create_response(
    status_code: int,
    message: str,
    data: Optional[Any] = None,
    error: Optional[str] = None,
) -> JSONResponse:
    """Tạo JSONResponse có cấu trúc nhất quán cho mọi endpoint.

    Format trả về:
    {
        "statusCode": 200,
        "message": "...",
        "error": null,
        "data": { ... }
    }
    """
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            "statusCode": status_code,
            "error": error,
            "message": message,
            "data": jsonable_encoder(data) if data is not None else None,
        }),
    )

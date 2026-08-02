from typing import Any, Optional
from fastapi.responses import JSONResponse

"""Response utility functions."""


def success_response(data: Any = None, message: str = "Success") -> JSONResponse:
    """Create a standardized success response."""
    return JSONResponse(content={
        "success": True,
        "message": message,
        "data": data,
    })


def error_response(message: str, status_code: int = 400) -> JSONResponse:
    """Create a standardized error response."""
    return JSONResponse(
        content={
            "success": False,
            "message": message,
            "data": None,
        },
        status_code=status_code,
    )


def pagination_response(
    items: list,
    page: int,
    page_size: int,
    total: int
) -> JSONResponse:
    """Create a standardized pagination response."""
    return JSONResponse(content={
        "success": True,
        "data": {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    })

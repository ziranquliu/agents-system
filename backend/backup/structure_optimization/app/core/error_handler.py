"""Standardized error responses"""
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any, Dict


class APIError(Exception):
    """Base API Error"""
    def __init__(self, status_code: int, message: str, code: str = None):
        self.status_code = status_code
        self.message = message
        self.code = code or "UNKNOWN_ERROR"


class ValidationError(APIError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(422, message, "VALIDATION_ERROR")


class AuthenticationError(APIError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(401, message, "AUTHENTICATION_ERROR")


class AuthorizationError(APIError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(403, message, "AUTHORIZATION_ERROR")


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(404, message, "NOT_FOUND")


class ConflictError(APIError):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(409, message, "CONFLICT")


class InternalError(APIError):
    def __init__(self, message: str = "Internal server error"):
        super().__init__(500, message, "INTERNAL_ERROR")


def create_error_response(status_code: int, message: str, code: str = None) -> Dict[str, Any]:
    """Create standardized error response"""
    return {
        "success": False,
        "error": {
            "code": code or f"ERROR_{status_code}",
            "message": message,
            "status_code": status_code
        }
    }


def create_success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """Create standardized success response"""
    return {
        "success": True,
        "data": data,
        "message": message
    }


async def custom_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Custom exception handler for standardized error responses"""
    if isinstance(exc, APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(exc.status_code, exc.message, exc.code)
        )
    
    # Log the unexpected error
    import logging
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=create_error_response(500, "An unexpected error occurred")
    )

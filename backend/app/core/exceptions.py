from typing import Any, Optional

"""Custom exception classes for the application."""



class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: int = 400,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(APIError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )


class AuthenticationError(APIError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationError(APIError):
    """Exception for authorization errors."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403
        )


class NotFoundError(APIError):
    """Exception for not found errors."""
    
    def __init__(self, resource: str, id: Optional[str] = None):
        message = f"{resource} not found"
        if id:
            message = f"{resource} with id {id} not found"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404
        )


class ConflictError(APIError):
    """Exception for conflict errors."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409
        )


class RateLimitError(APIError):
    """Exception for rate limit errors."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT",
            status_code=429
        )


class DatabaseError(APIError):
    """Exception for database errors."""
    
    def __init__(self, message: str = "Database error occurred"):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500
        )


class ExternalServiceError(APIError):
    """Exception for external service errors."""
    
    def __init__(self, service: str, message: str = ""):
        full_message = f"External service error: {service}"
        if message:
            full_message += f": {message}"
        super().__init__(
            message=full_message,
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503
        )

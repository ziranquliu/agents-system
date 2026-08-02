"""
Base module with common dependencies and mixins.

This module provides shared dependencies, mixins, and utility classes
to reduce code duplication across the application.

Usage:
    from app.core.base import get_db, get_current_user, DatabaseMixin, PaginationMixin
"""

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.session import get_db as _get_db
from app.models.user import User
from app.core.security import get_current_user as _get_current_user

# ============================================================================
# Re-export common dependencies for convenience
# ============================================================================

# Database dependency
get_db = _get_db

# Authentication dependency
get_current_user = _get_current_user

# ORM loading strategies
select_inload = selectinload
joined_inload = joinedload

# ============================================================================
# Type definitions
# ============================================================================

T = TypeVar("T")

# ============================================================================
# Mixin Classes
# ============================================================================

class DatabaseMixin:
    """
    Mixin class providing common database operations.
    
    Usage:
        class MyService(DatabaseMixin):
            async def __init__(self, db: AsyncSession):
                self.db = db
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.db.commit()
    
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.db.rollback()
    
    async def flush(self) -> None:
        """Flush pending changes."""
        await self.db.flush()
    
    async def refresh(self, instance: Any) -> None:
        """Refresh an instance from the database."""
        await self.db.refresh(instance)


class PaginationMixin:
    """
    Mixin class providing pagination utilities.
    
    Usage:
        class MyService(PaginationMixin):
            def paginate(self, items, page, page_size):
                return self.create_pagination(items, page, page_size)
    """
    
    @staticmethod
    def create_pagination(
        items: list,
        page: int,
        page_size: int,
        total: Optional[int] = None
    ) -> dict:
        """
        Create pagination response.
        
        Args:
            items: List of items to paginate
            page: Page number (1-indexed)
            page_size: Number of items per page
            total: Total number of items (optional, will be calculated if not provided)
        
        Returns:
            Dictionary with pagination metadata
        """
        if total is None:
            total = len(items)
        
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]
        
        return {
            "items": paginated_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": page < (total + page_size - 1) // page_size,
            "has_prev": page > 1,
        }


class TimestampMixin:
    """
    Mixin class providing timestamp utilities.
    
    Usage:
        from datetime import datetime, timezone
        
        class MyModel:
            created_at = Column(DateTime, default=datetime.now(timezone.utc))
            updated_at = Column(DateTime, onupdate=datetime.now(timezone.utc))
    """
    
    @staticmethod
    def now_utc():
        """Get current UTC datetime."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)


# ============================================================================
# Response Helpers
# ============================================================================

def success_response(data: Any = None, message: str = "Success") -> dict:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Success message
    
    Returns:
        Dictionary with success response structure
    """
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(
    message: str,
    code: Optional[str] = None,
    details: Optional[dict] = None
) -> dict:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        code: Error code (optional)
        details: Error details (optional)
    
    Returns:
        Dictionary with error response structure
    """
    response = {
        "success": False,
        "message": message,
        "data": None,
    }
    
    if code:
        response["code"] = code
    if details:
        response["details"] = details
    
    return response


def pagination_response(
    items: list,
    page: int,
    page_size: int,
    total: int
) -> dict:
    """
    Create a standardized pagination response.
    
    Args:
        items: List of items
        page: Current page number
        page_size: Items per page
        total: Total number of items
    
    Returns:
        Dictionary with pagination response structure
    """
    return {
        "success": True,
        "message": "Success",
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page < (total + page_size - 1) // page_size,
                "has_prev": page > 1,
            }
        },
    }


# ============================================================================
# Decorators
# ============================================================================

def log_execution(func: Callable) -> Callable:
    """
    Decorator to log function execution.
    
    Usage:
        @log_execution
        async def my_function():
            pass
    """
    import logging
    logger = logging.getLogger(__name__)
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        logger.debug(f"Completed {func.__name__}")
        return result
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger.debug(f"Calling async {func.__name__}")
        result = await func(*args, **kwargs)
        logger.debug(f"Completed async {func.__name__}")
        return result
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Decorator to retry function calls on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Delay between retries in seconds
    
    Usage:
        @retry(max_attempts=3, delay=1.0)
        async def my_function():
            pass
    """
    import time
    import logging
    logger = logging.getLogger(__name__)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    time.sleep(delay)
        return wrapper
    
    return decorator


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_uuid(uuid_str: str) -> bool:
    """
    Validate UUID format.
    
    Args:
        uuid_str: UUID string to validate
    
    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, uuid_str.lower()))


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Sanitize string input.
    
    Args:
        text: Input text
        max_length: Maximum length
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Trim and limit length
    text = text.strip()[:max_length]
    
    return text

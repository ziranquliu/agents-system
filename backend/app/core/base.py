"""
Base module with common dependencies, mixins, and utilities.

Re-exports shared dependencies for convenience; provides DatabaseMixin,
PaginationMixin, TimestampMixin, response helpers, and decorators.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.session import get_db as _get_db
try:
    from app.core.security import get_current_user as _get_current_user
except ImportError:
    from app.services.auth_service import get_current_user as _get_current_user

logger = logging.getLogger(__name__)

# ============================================================================
# Re-export common dependencies for convenience
# ============================================================================

get_db = _get_db
get_current_user = _get_current_user

# ORM loading strategies (alias for convenience)
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
    """Mixin providing common async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def flush(self) -> None:
        await self.db.flush()

    async def refresh(self, instance: Any) -> None:
        await self.db.refresh(instance)


class PaginationMixin:
    """Mixin providing pagination utilities."""

    @staticmethod
    def create_pagination(
        items: list,
        page: int,
        page_size: int,
        total: Optional[int] = None,
    ) -> dict:
        if total is None:
            total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]
        total_pages = (total + page_size - 1) // page_size

        return {
            "items": paginated_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }


class TimestampMixin:
    """Mixin providing UTC timestamp utilities."""

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)


# ============================================================================
# Response Helpers
# ============================================================================


def success_response(data: Any = None, message: str = "Success") -> dict:
    return {"success": True, "message": message, "data": data}


def error_response(
    message: str,
    code: Optional[str] = None,
    details: Optional[dict] = None,
) -> dict:
    response: dict[str, Any] = {
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
    total: int,
) -> dict:
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "message": "Success",
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
    }


# ============================================================================
# Decorators
# ============================================================================


def log_execution(func: Callable) -> Callable:
    """Decorator to log function entry and exit."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("Calling %s", func.__name__)
        result = func(*args, **kwargs)
        logger.debug("Completed %s", func.__name__)
        return result

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger.debug("Calling async %s", func.__name__)
        result = await func(*args, **kwargs)
        logger.debug("Completed async %s", func.__name__)
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0):
    """Decorator to retry function calls on failure. Supports both sync and async."""

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
                        "Attempt %d/%d failed for %s: %s",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        e,
                    )
                    time.sleep(delay)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        e,
                    )
                    await asyncio.sleep(delay)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# ============================================================================
# Validation Helpers
# ============================================================================

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{4}\-[0-9a-f]{12}$"
)


def validate_email(email: str) -> bool:
    """Validate email format."""
    return bool(_EMAIL_RE.match(email))


def validate_uuid(uuid_str: str) -> bool:
    """Validate UUID format (case-insensitive)."""
    return bool(_UUID_RE.match(uuid_str.lower()))


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Remove HTML tags and trim text to max_length."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()[:max_length]

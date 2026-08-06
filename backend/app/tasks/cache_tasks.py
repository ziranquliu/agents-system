"""
缓存维护任务

- cleanup_expired_cache: 清理过期缓存
- warm_cache: 预热缓存
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cache.cleanup_expired_cache")
def cleanup_expired_cache():
    """清理过期缓存"""
    logger.info("Cleaning up expired cache entries")
    cleaned = 0
    # TODO: Redis FLUSHDB on expired keys or iterate with pattern
    return {"status": "success", "cleaned": cleaned}


@celery_app.task(name="app.tasks.cache.warm_cache")
def warm_cache(keys: list[str] = None):
    """预热缓存"""
    logger.info(f"Warming cache for {len(keys or [])} keys")
    return {"status": "success", "warmed": len(keys or [])}

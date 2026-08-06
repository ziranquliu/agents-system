"""
日志轮转任务

- rotate_logs: 日志轮转
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.logs.rotate_logs")
def rotate_logs(max_days: int = 30):
    """日志轮转"""
    logger.info(f"Rotating logs older than {max_days} days")
    return {"status": "success", "rotated": 0}

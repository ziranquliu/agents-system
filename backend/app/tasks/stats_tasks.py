"""
统计重算任务

- recalculate_statistics: 重算所有统计指标
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.stats.recalculate_statistics")
def recalculate_statistics():
    """重算统计分析"""
    logger.info("Recalculating all statistics")
    return {"status": "success", "metrics_recalculated": 0}

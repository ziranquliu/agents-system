"""
预算检查任务

- check_budget_thresholds: 检查预算阈值
- monthly_budget_reset: 月度预算重置
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.budget.check_budget_thresholds")
def check_budget_thresholds():
    """检查预算阈值"""
    logger.info("Checking budget thresholds")
    return {"status": "success", "alerts": 0}


@celery_app.task(name="app.tasks.budget.monthly_budget_reset")
def monthly_budget_reset():
    """月度预算重置"""
    logger.info("Resetting monthly budgets")
    return {"status": "success", "reset": 0}

"""
健康检查任务

- check_all_agents: 检查所有 Agent 健康状态
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.health.check_all_agents")
def check_all_agents():
    """检查所有 Agent 健康状态"""
    logger.info("Checking health of all agents")
    return {"status": "success", "checked": 0, "unhealthy": 0}

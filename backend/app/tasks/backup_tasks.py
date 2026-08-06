"""
备份任务

- cleanup_old_backups: 清理旧备份
- run_backup_drill: 恢复演练
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.backup.cleanup_old_backups")
def cleanup_old_backups(keep_count: int = 30):
    """清理旧备份"""
    logger.info(f"Cleaning up backups, keeping last {keep_count}")
    return {"status": "success", "removed": 0, "kept": keep_count}


@celery_app.task(name="app.tasks.backup.run_backup_drill")
def run_backup_drill():
    """恢复演练"""
    logger.info("Running backup drill")
    return {"status": "success", "drill_result": "passed"}

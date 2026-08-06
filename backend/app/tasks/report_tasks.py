"""
报告任务

- generate_daily_report: 日报
- generate_weekly_report: 周报
- generate_monthly_report: 月报
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.report.generate_daily_report")
def generate_daily_report():
    """生成日报"""
    logger.info("Generating daily report")
    return {"status": "success", "report_type": "daily"}


@celery_app.task(name="app.tasks.report.generate_weekly_report")
def generate_weekly_report():
    """生成周报"""
    logger.info("Generating weekly report")
    return {"status": "success", "report_type": "weekly"}


@celery_app.task(name="app.tasks.report.generate_monthly_report")
def generate_monthly_report():
    """生成月报"""
    logger.info("Generating monthly report")
    return {"status": "success", "report_type": "monthly"}

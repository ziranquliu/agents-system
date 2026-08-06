"""
Celery 异步任务队列配置

功能:
- Celery Beat 定时任务调度（替代 APScheduler 用于分布式场景）
- Redis 作为 Broker + Result Backend
- 常量任务定义（会话清理/缓存清理/索引重建/统计重算）
"""

import os
from celery import Celery
from celery.schedules import crontab

# 创建 Celery 应用
celery_app = Celery(
    "agent_system",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
)

# Celery 配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 结果过期时间（1小时）
    result_expires=3600,

    # 任务路由
    task_routes={
        "app.tasks.session.*": {"queue": "maintenance"},
        "app.tasks.cache.*": {"queue": "maintenance"},
        "app.tasks.index.*": {"queue": "maintenance"},
        "app.tasks.stats.*": {"queue": "analytics"},
        "app.tasks.backup.*": {"queue": "backup"},
        "app.tasks.report.*": {"queue": "analytics"},
        "app.tasks.alert.*": {"queue": "alerts"},
    },

    # 默认队列
    task_default_queue="default",

    # Worker 配置
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,

    # 任务超时
    task_soft_time_limit=300,
    task_time_limit=600,

    # Beat 定时任务
    beat_schedule={
        # 会话清理 — 每日 2:00
        "session-cleanup-daily": {
            "task": "app.tasks.session.cleanup_expired_sessions",
            "schedule": crontab(hour=2, minute=0),
            "kwargs": {"max_age_days": 30},
        },

        # 缓存清理 — 每日 3:00
        "cache-cleanup-daily": {
            "task": "app.tasks.cache.cleanup_expired_cache",
            "schedule": crontab(hour=3, minute=0),
        },

        # 向量索引重建 — 每周日 4:00
        "index-rebuild-weekly": {
            "task": "app.tasks.index.rebuild_vector_index",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
        },

        # 统计重算 — 每日 1:00
        "stats-rebuild-daily": {
            "task": "app.tasks.stats.recalculate_statistics",
            "schedule": crontab(hour=1, minute=0),
        },

        # 日报 — 每日 8:00
        "report-daily": {
            "task": "app.tasks.report.generate_daily_report",
            "schedule": crontab(hour=8, minute=0),
        },

        # 周报 — 每周一 9:00
        "report-weekly": {
            "task": "app.tasks.report.generate_weekly_report",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
        },

        # 月报 — 每月1日 10:00
        "report-monthly": {
            "task": "app.tasks.report.generate_monthly_report",
            "schedule": crontab(hour=10, minute=0, day_of_month=1),
        },

        # 健康检查 — 每 5 分钟
        "health-check": {
            "task": "app.tasks.health.check_all_agents",
            "schedule": crontab(minute="*/5"),
        },

        # 预算检查 — 每小时
        "budget-check-hourly": {
            "task": "app.tasks.budget.check_budget_thresholds",
            "schedule": crontab(minute=0, hour="*/1"),
        },

        # 备份清理 — 每月15日 5:00
        "backup-cleanup-monthly": {
            "task": "app.tasks.backup.cleanup_old_backups",
            "schedule": crontab(hour=5, minute=0, day_of_month=15),
            "kwargs": {"keep_count": 30},
        },

        # 备份验证演练 — 每周日 6:00
        "backup-drill-weekly": {
            "task": "app.tasks.backup.run_backup_drill",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),
        },

        # 月度自动重置 — 每月1日 0:00
        "budget-monthly-reset": {
            "task": "app.tasks.budget.monthly_budget_reset",
            "schedule": crontab(hour=0, minute=0, day_of_month=1),
        },

        # 日志轮转 — 每日 4:30
        "log-rotation-daily": {
            "task": "app.tasks.logs.rotate_logs",
            "schedule": crontab(hour=4, minute=30),
        },
    },

    # 定时任务时区
    beat_schedule_filename="celerybeat-schedule",
)

# 自动发现任务模块
celery_app.autodiscover_tasks(["app.tasks"])

"""
统一更新检测中心 — 更新快照/回滚 模型 — 统一导出

所有定义已合并至 update.py，此文件仅做 re-export 保持向后兼容。
"""
from app.models.update import (  # noqa: F401
    UpdateSnapshot,
    UpdateLog,
)

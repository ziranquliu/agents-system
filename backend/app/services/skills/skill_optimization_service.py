import json
import time
from collections import OrderedDict
from typing import Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.skill import SkillBinding, Skill

"""
Skill 使用优化服务 - 缓存/DAG优化/性能监控
"""


# 简单的 LRU 缓存（进程内）
class LRUCache:
    """LRU 缓存"""

    def __init__(self, capacity: int = 100):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def size(self) -> int:
        return len(self.cache)

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


# 全局缓存实例
skill_config_cache = LRUCache(capacity=200)
skill_execution_times = {}  # skill_id -> list of execution durations


def get_cache_stats() -> dict:
    """获取缓存统计"""
    return {
        "cache_type": "LRU (in-memory)",
        "capacity": skill_config_cache.capacity,
        "size": skill_config_cache.size(),
        "hits": skill_config_cache.hits,
        "misses": skill_config_cache.misses,
        "hit_rate": round(skill_config_cache.hit_rate() * 100, 2),
    }


def clear_cache() -> dict:
    """清除缓存"""
    skill_config_cache.clear()
    return {"message": "缓存已清除", "stats": get_cache_stats()}


def record_execution(skill_id: str, duration_ms: float) -> None:
    """记录执行时间"""
    if skill_id not in skill_execution_times:
        skill_execution_times[skill_id] = []
    skill_execution_times[skill_id].append(duration_ms)
    # 只保留最近 100 条
    if len(skill_execution_times[skill_id]) > 100:
        skill_execution_times[skill_id] = skill_execution_times[skill_id][-100:]


def get_execution_stats(skill_id: Optional[str] = None) -> dict:
    """获取执行统计"""
    if skill_id:
        times = skill_execution_times.get(skill_id, [])
        if not times:
            return {"skill_id": skill_id, "executions": 0}
        return {
            "skill_id": skill_id,
            "executions": len(times),
            "avg_duration_ms": round(sum(times) / len(times), 2),
            "min_duration_ms": round(min(times), 2),
            "max_duration_ms": round(max(times), 2),
            "total_duration_ms": round(sum(times), 2),
        }
    else:
        total = sum(len(v) for v in skill_execution_times.values())
        if total == 0:
            return {"total_skills": 0, "total_executions": 0}
        all_times = [t for times in skill_execution_times.values() for t in times]
        return {
            "total_skills": len(skill_execution_times),
            "total_executions": total,
            "avg_duration_ms": round(sum(all_times) / len(all_times), 2),
        }


def compute_dag_plan(skill_ids: list[str], skill_deps: dict[str, list[str]]) -> list[list[str]]:
    """计算 DAG 执行计划（拓扑排序分层）

    输入：
    - skill_ids: 所有参与的 skill ID 列表
    - skill_deps: skill_id -> [依赖的 skill_id]

    输出：
    - 分层列表，每层可以并行执行
    """
    # 构建入度表
    in_degree = {sid: 0 for sid in skill_ids}
    dep_map = {sid: [] for sid in skill_ids}

    for sid in skill_ids:
        deps = skill_deps.get(sid, [])
        for dep in deps:
            if dep in dep_map:
                dep_map[dep].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

    # Kahn 拓扑排序
    queue = [sid for sid in skill_ids if in_degree.get(sid, 0) == 0]
    levels = []

    while queue:
        level = list(queue)
        levels.append(level)
        queue = []
        for sid in level:
            for next_sid in dep_map.get(sid, []):
                in_degree[next_sid] -= 1
                if in_degree[next_sid] == 0:
                    queue.append(next_sid)

    return levels


async def get_skill_dependencies(db: AsyncSession) -> dict:
    """获取所有 Skill 的依赖关系"""

    result = await db.execute(
        select(SkillBinding.skill_id, Skill.name)
        .join(Skill, SkillBinding.skill_id == Skill.id)
    )
    bindings = result.all()

    # 构建依赖图（简化为基于 Agent 的共用关系）
    deps = {}
    skill_names = {}
    for binding in bindings:
        sid = binding[0]
        sname = binding[1]
        if sid not in deps:
            deps[sid] = []
        skill_names[sid] = sname

    return {"dependencies": deps, "skill_names": skill_names}

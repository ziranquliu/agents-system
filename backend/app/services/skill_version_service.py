"""
Skill 版本管理与依赖系统 — SemVer 2.0 + 依赖 DAG

功能:
- SemVer 2.0 版本规范（MAJOR.MINOR.PATCH）
- 依赖 DAG 解析（拓扑排序、环检测）
- 版本锁定/浮动
- 兼容性预检
- 多版本共存
- 跨 Agent Skill 共享
"""

import logging
import re
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VersionConstraint(str, Enum):
    EXACT = "exact"         # =1.2.3
    COMPATIBLE = "compatible"  # >=1.2.0 <2.0.0 (^1.2.3)
    RANGE = "range"         # >=1.0.0 <=2.0.0
    WILDCARD = "wildcard"   # 1.*


@dataclass
class SemVer:
    """语义化版本号"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: str = ""

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        """解析版本字符串"""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version_str.strip())
        if not match:
            raise ValueError(f"Invalid version: {version_str}")
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
        )

    def __str__(self) -> str:
        v = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            v += f"-{self.prerelease}"
        return v

    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other):
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other):
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other):
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def __eq__(self, other):
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __hash__(self):
        return hash((self.major, self.minor, self.patch))

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)


@dataclass
class SkillDependency:
    """Skill 依赖"""
    name: str = ""
    constraint: VersionConstraint = VersionConstraint.COMPATIBLE
    version_spec: str = ""      # 如 "^1.2.0", "=2.0.0", ">=1.0.0"
    optional: bool = False
    resolved_version: str = ""

    def satisfies(self, version: SemVer) -> bool:
        """检查版本是否满足约束"""
        if self.constraint == VersionConstraint.EXACT:
            return SemVer.parse(self.version_spec) == version
        elif self.constraint == VersionConstraint.COMPATIBLE:
            # ^1.2.3 → >=1.2.3 <2.0.0
            target = SemVer.parse(self.version_spec)
            return version >= target and version.major == target.major
        elif self.constraint == VersionConstraint.RANGE:
            parts = self.version_spec.split()
            if len(parts) == 2:
                low = SemVer.parse(parts[0].lstrip(">=<"))
                high = SemVer.parse(parts[1].lstrip(">=<"))
                return low <= version <= high
        elif self.constraint == VersionConstraint.WILDCARD:
            target = SemVer.parse(self.version_spec)
            return version.major == target.major
        return True


@dataclass
class SkillVersion:
    """Skill 版本"""
    skill_id: str = ""
    version: str = ""          # SemVer string
    description: str = ""
    author: str = ""
    dependencies: list[SkillDependency] = field(default_factory=list)
    compatible_agents: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    is_deprecated: bool = False
    published_at: Optional[datetime] = None
    yanked: bool = False


@dataclass
class VersionLock:
    """版本锁定"""
    skill_id: str = ""
    locked_version: str = ""
    locked_by: str = ""        # user_id / system
    locked_at: Optional[datetime] = None
    reason: str = ""


@dataclass
class CompatibilityCheck:
    """兼容性预检结果"""
    skill_id: str = ""
    target_version: str = ""
    compatible: bool = True
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class SkillVersionService:
    """
    Skill 版本管理与依赖系统

    - SemVer 2.0 解析与比较
    - 依赖 DAG 拓扑排序 + 环检测
    - 版本锁定/浮动
    - 兼容性预检
    - 跨 Agent 共享
    """

    def __init__(self):
        self._versions: dict[str, list[SkillVersion]] = {}  # skill_id → versions
        self._locks: dict[str, VersionLock] = {}             # skill_id → lock
        self._agent_bindings: dict[str, list[str]] = {}      # agent_id → [skill_id:version]
        self._shared_skills: dict[str, list[str]] = {}       # skill_id → [agent_ids]

    # ----------------------------------------------------------
    # 版本管理
    # ----------------------------------------------------------

    def publish_version(
        self,
        skill_id: str,
        version_str: str,
        description: str = "",
        author: str = "",
        dependencies: Optional[list[SkillDependency]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> SkillVersion:
        """发布新版本"""
        ver = SemVer.parse(version_str)
        sv = SkillVersion(
            skill_id=skill_id,
            version=str(ver),
            description=description,
            author=author,
            dependencies=dependencies or [],
            config=config or {},
            published_at=datetime.now(timezone.utc),
        )
        if skill_id not in self._versions:
            self._versions[skill_id] = []
        self._versions[skill_id].append(sv)
        logger.info(f"Published {skill_id} v{ver}")
        return sv

    def get_versions(self, skill_id: str) -> list[dict[str, Any]]:
        """获取所有版本"""
        versions = self._versions.get(skill_id, [])
        return [
            {
                "version": v.version,
                "description": v.description,
                "author": v.author,
                "dependencies": [
                    {"name": d.name, "constraint": d.constraint.value, "version_spec": d.version_spec}
                    for d in v.dependencies
                ],
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "deprecated": v.is_deprecated,
                "yanked": v.yanked,
            }
            for v in versions
        ]

    def get_latest_version(self, skill_id: str) -> Optional[SkillVersion]:
        """获取最新版本"""
        versions = self._versions.get(skill_id, [])
        if not versions:
            return None
        valid = [v for v in versions if not v.yanked and not v.is_deprecated]
        if not valid:
            return None
        return max(valid, key=lambda v: SemVer.parse(v.version))

    def get_compatible_version(
        self,
        skill_id: str,
        constraint: str = "",
    ) -> Optional[SkillVersion]:
        """获取兼容版本"""
        versions = self._versions.get(skill_id, [])
        valid = [v for v in versions if not v.yanked and not v.is_deprecated]

        if not constraint:
            return valid[-1] if valid else None

        target = SemVer.parse(constraint.lstrip(">=<^~"))
        for v in reversed(valid):
            ver = SemVer.parse(v.version)
            if ver >= target:
                return v
        return valid[0] if valid else None

    def yank_version(self, skill_id: str, version_str: str) -> bool:
        """撤回版本"""
        for v in self._versions.get(skill_id, []):
            if v.version == version_str:
                v.yanked = True
                return True
        return False

    def deprecate_version(self, skill_id: str, version_str: str, replacement: str = "") -> bool:
        """标记弃用"""
        for v in self._versions.get(skill_id, []):
            if v.version == version_str:
                v.is_deprecated = True
                if replacement:
                    v.description += f" [DEPRECATED: use {replacement}]"
                return True
        return False

    # ----------------------------------------------------------
    # 版本锁定/浮动
    # ----------------------------------------------------------

    def lock_version(
        self,
        skill_id: str,
        version: str,
        locked_by: str = "system",
        reason: str = "",
    ) -> VersionLock:
        """锁定版本"""
        lock = VersionLock(
            skill_id=skill_id,
            locked_version=version,
            locked_by=locked_by,
            locked_at=datetime.now(timezone.utc),
            reason=reason,
        )
        self._locks[skill_id] = lock
        logger.info(f"Locked {skill_id} to v{version}")
        return lock

    def unlock_version(self, skill_id: str) -> bool:
        """解锁版本"""
        if skill_id in self._locks:
            del self._locks[skill_id]
            return True
        return False

    def get_lock(self, skill_id: str) -> Optional[dict[str, Any]]:
        lock = self._locks.get(skill_id)
        if lock:
            return {
                "skill_id": lock.skill_id,
                "locked_version": lock.locked_version,
                "locked_by": lock.locked_by,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "reason": lock.reason,
            }
        return None

    def get_effective_version(self, skill_id: str) -> Optional[str]:
        """获取实际生效版本（优先锁定）"""
        lock = self._locks.get(skill_id)
        if lock:
            return lock.locked_version
        latest = self.get_latest_version(skill_id)
        return latest.version if latest else None

    # ----------------------------------------------------------
    # 依赖 DAG 解析
    # ----------------------------------------------------------

    def resolve_dependencies(
        self,
        skill_id: str,
        version: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        解析依赖 DAG

        Returns:
            {
                "resolved": True/False,
                "order": ["dep1", "dep2", "skill"],
                "conflicts": [...],
                "graph": {"skill": ["dep1", "dep2"]},
            }
        """
        # 获取目标版本
        if version:
            target_version = SemVer.parse(version)
        else:
            latest = self.get_latest_version(skill_id)
            if not latest:
                return {"resolved": False, "error": f"Skill {skill_id} not found"}
            target_version = SemVer.parse(latest.version)

        # 构建依赖图
        graph: dict[str, list[str]] = {}
        all_versions: dict[str, list[SemVer]] = {}

        def build_graph(sid: str, depth: int = 0):
            if depth > 10:
                return
            versions = self._versions.get(sid, [])
            for sv in versions:
                ver = SemVer.parse(sv.version)
                if sid not in all_versions:
                    all_versions[sid] = []
                all_versions[sid].append(ver)

                if sid not in graph:
                    graph[sid] = []
                for dep in sv.dependencies:
                    graph[sid].append(dep.name)
                    if dep.name not in graph:
                        build_graph(dep.name, depth + 1)

        build_graph(skill_id)

        # 环检测（Kahn's 算法）
        in_degree: dict[str, int] = defaultdict(int)
        for node, deps in graph.items():
            if node not in in_degree:
                in_degree[node] = 0
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        has_cycle = len(order) != len(in_degree)

        # 版本兼容性检查
        conflicts = []
        if not has_cycle:
            for sid in order:
                if sid == skill_id:
                    continue
                versions = all_versions.get(sid, [])
                dep_spec = ""
                for node_deps in graph.values():
                    for dep_name in node_deps:
                        dep_spec = dep_name
                if not versions:
                    target_sv = self.get_latest_version(sid)
                    if target_sv:
                        conflicts.append({
                            "skill": sid,
                            "issue": "no matching version",
                        })

        return {
            "resolved": not has_cycle and not conflicts,
            "order": order,
            "conflicts": conflicts,
            "graph": graph,
            "has_cycle": has_cycle,
        }

    # ----------------------------------------------------------
    # 兼容性预检
    # ----------------------------------------------------------

    def check_compatibility(
        self,
        skill_id: str,
        version: str,
        agent_skills: Optional[dict[str, str]] = None,
    ) -> CompatibilityCheck:
        """兼容性预检"""
        result = CompatibilityCheck(skill_id=skill_id, target_version=version)

        versions = self._versions.get(skill_id, [])
        target = SemVer.parse(version)

        # 检查版本是否存在
        found = any(SemVer.parse(v.version) == target for v in versions)
        if not found:
            result.compatible = False
            result.conflicts.append({"issue": f"Version {version} not found"})

        # 检查依赖冲突
        for sv in versions:
            if SemVer.parse(sv.version) == target:
                for dep in sv.dependencies:
                    if agent_skills and dep.name in agent_skills:
                        installed_ver = SemVer.parse(agent_skills[dep.name])
                        if not dep.satisfies(installed_ver):
                            result.compatible = False
                            result.conflicts.append({
                                "dependency": dep.name,
                                "required": dep.version_spec,
                                "installed": str(installed_ver),
                            })
                    elif not dep.optional:
                        result.suggestions.append(f"Install dependency: {dep.name} {dep.version_spec}")

        return result

    # ----------------------------------------------------------
    # 跨 Agent 共享
    # ----------------------------------------------------------

    def share_skill(
        self,
        skill_id: str,
        source_agent_id: str,
        target_agent_ids: list[str],
    ) -> dict[str, Any]:
        """跨 Agent 共享 Skill"""
        if skill_id not in self._shared_skills:
            self._shared_skills[skill_id] = []

        added = []
        for agent_id in target_agent_ids:
            if agent_id not in self._shared_skills[skill_id]:
                self._shared_skills[skill_id].append(agent_id)
                added.append(agent_id)

        return {
            "skill_id": skill_id,
            "shared_with": added,
            "total_sharers": len(self._shared_skills[skill_id]),
        }

    def get_shared_agents(self, skill_id: str) -> list[str]:
        """获取共享了某 Skill 的 Agent"""
        return self._shared_skills.get(skill_id, [])

    def unshare_skill(self, skill_id: str, agent_id: str) -> bool:
        if skill_id in self._shared_skills:
            if agent_id in self._shared_skills[skill_id]:
                self._shared_skills[skill_id].remove(agent_id)
                return True
        return False

    # ----------------------------------------------------------
    # 版本矩阵
    # ----------------------------------------------------------

    def get_version_matrix(self) -> dict[str, Any]:
        """获取版本矩阵（所有 Skill 的所有版本）"""
        matrix = {}
        for skill_id, versions in self._versions.items():
            matrix[skill_id] = {
                "latest": versions[-1].version if versions else "",
                "total_versions": len(versions),
                "versions": [v.version for v in versions],
                "locked": self._locks.get(skill_id, None) is not None,
            }
        return matrix

"""
技能组合优化服务

功能:
- 技能组合推荐
- 冲突检测
- 依赖分析
- 性能影响评估
- 组合评分
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    """技能元数据"""
    id: str = ""
    name: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他技能
    conflicts: list[str] = field(default_factory=list)  # 冲突的技能
    resource_cost: float = 1.0  # 资源消耗系数 (0-5)
    performance_impact: float = 0  # 延迟影响 (ms)
    enable_count: int = 0  # 被启用次数
    avg_rating: float = 0  # 平均评分 (0-5)


@dataclass
class SkillCombination:
    """技能组合"""
    skill_ids: list[str] = field(default_factory=list)
    score: float = 0
    conflicts: list[str] = field(default_factory=list)
    total_resource_cost: float = 0
    estimated_latency_impact: float = 0
    synergy_score: float = 0  # 协同效应
    coverage_score: float = 0  # 功能覆盖


@dataclass
class ConflictInfo:
    """冲突信息"""
    skill_a: str = ""
    skill_b: str = ""
    reason: str = ""
    severity: str = "warning"  # warning / critical


class SkillCombinationService:
    """
    技能组合优化服务

    - 冲突检测 (硬冲突/软冲突)
    - 依赖分析 (DAG)
    - 协同评分
    - 推荐引擎
    """

    def __init__(self):
        self._skills: dict[str, SkillMeta] = {}
        self._conflict_rules: list[dict] = []
        self._combination_history: list[dict] = []

    # ----------------------------------------------------------
    # 技能管理
    # ----------------------------------------------------------

    def register_skill(self, skill: dict) -> dict:
        """注册技能"""
        meta = SkillMeta(**skill)
        self._skills[meta.id] = meta
        return {"skill_id": meta.id, "registered": True}

    def get_skill(self, skill_id: str) -> Optional[dict]:
        s = self._skills.get(skill_id)
        if not s:
            return None
        return {
            "id": s.id, "name": s.name, "category": s.category,
            "tags": s.tags, "dependencies": s.dependencies,
            "conflicts": s.conflicts, "resource_cost": s.resource_cost,
        }

    def list_skills(self, category: str = "") -> list[dict]:
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return [
            {"id": s.id, "name": s.name, "category": s.category, "tags": s.tags}
            for s in skills
        ]

    def add_conflict_rule(self, rule: dict):
        """添加冲突规则"""
        self._conflict_rules.append(rule)

    # ----------------------------------------------------------
    # 冲突检测
    # ----------------------------------------------------------

    def detect_conflicts(self, skill_ids: list[str]) -> list[ConflictInfo]:
        """检测技能组合中的冲突"""
        conflicts = []
        skills = [self._skills.get(sid) for sid in skill_ids if sid in self._skills]

        # 声明式冲突
        for i, a in enumerate(skills):
            for b in skills[i + 1:]:
                if b.id in a.conflicts or a.id in b.conflicts:
                    conflicts.append(ConflictInfo(
                        skill_a=a.id,
                        skill_b=b.id,
                        reason="声明冲突",
                        severity="critical",
                    ))

        # 规则冲突
        skill_set = set(skill_ids)
        for rule in self._conflict_rules:
            rule_skills = set(rule.get("skills", []))
            if rule_skills.issubset(skill_set):
                conflicts.append(ConflictInfo(
                    skill_a=rule.get("skills", [""])[0],
                    skill_b=rule.get("skills", ["", ""])[1] if len(rule.get("skills", [])) > 1 else "",
                    reason=rule.get("reason", "规则冲突"),
                    severity=rule.get("severity", "warning"),
                ))

        # 类别冲突 (同类别资源竞争)
        category_count: dict[str, list[str]] = defaultdict(list)
        for s in skills:
            category_count[s.category].append(s.id)
        for cat, sids in category_count.items():
            if len(sids) > 2:
                conflicts.append(ConflictInfo(
                    skill_a=sids[0],
                    skill_b=sids[1],
                    reason=f"类别 '{cat}' 技能过多 ({len(sids)}), 可能存在资源竞争",
                    severity="warning",
                ))

        return conflicts

    # ----------------------------------------------------------
    # 依赖分析
    # ----------------------------------------------------------

    def check_dependencies(self, skill_ids: list[str]) -> dict:
        """检查依赖是否满足"""
        provided = set(skill_ids)
        missing = []
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill:
                for dep in skill.dependencies:
                    if dep not in provided:
                        missing.append({"skill": sid, "missing_dependency": dep})

        return {
            "all_satisfied": len(missing) == 0,
            "missing": missing,
        }

    def get_dependency_chain(self, skill_id: str) -> list[str]:
        """获取完整依赖链 (拓扑排序)"""
        visited = set()
        chain = []
        self._dfs_deps(skill_id, visited, chain)
        return chain

    def _dfs_deps(self, skill_id: str, visited: set, chain: list):
        if skill_id in visited:
            return
        visited.add(skill_id)
        skill = self._skills.get(skill_id)
        if skill:
            for dep in skill.dependencies:
                self._dfs_deps(dep, visited, chain)
        chain.append(skill_id)

    # ----------------------------------------------------------
    # 组合评分
    # ----------------------------------------------------------

    def score_combination(self, skill_ids: list[str]) -> SkillCombination:
        """评分技能组合"""
        skills = [self._skills.get(sid) for sid in skill_ids if sid in self._skills]
        conflicts = self.detect_conflicts(skill_ids)

        # 资源消耗
        total_cost = sum(s.resource_cost for s in skills)

        # 延迟影响
        total_latency = sum(s.performance_impact for s in skills)

        # 协同效应 (不同类别的技能越多, 协同越好)
        categories = {s.category for s in skills}
        synergy = min(100, len(categories) * 15)

        # 功能覆盖 (基于标签去重)
        all_tags = set()
        for s in skills:
            all_tags.update(s.tags)
        coverage = min(100, len(all_tags) * 8)

        # 综合评分
        critical_conflicts = sum(1 for c in conflicts if c.severity == "critical")
        warning_conflicts = sum(1 for c in conflicts if c.severity == "warning")

        score = 100
        score -= critical_conflicts * 30
        score -= warning_conflicts * 10
        score += synergy * 0.2
        score += coverage * 0.1
        score -= total_cost * 3
        score = max(0, min(100, score))

        return SkillCombination(
            skill_ids=skill_ids,
            score=round(score, 1),
            conflicts=[f"{c.skill_a} ↔ {c.skill_b}: {c.reason}" for c in conflicts],
            total_resource_cost=round(total_cost, 2),
            estimated_latency_impact=round(total_latency, 1),
            synergy_score=round(synergy, 1),
            coverage_score=round(coverage, 1),
        )

    # ----------------------------------------------------------
    # 推荐
    # ----------------------------------------------------------

    def recommend(
        self,
        purpose: str = "",
        max_skills: int = 5,
        exclude: Optional[list[str]] = None,
        include: Optional[list[str]] = None,
    ) -> list[dict]:
        """推荐技能组合"""
        candidates = list(self._skills.values())
        exclude_set = set(exclude or [])
        candidates = [s for s in candidates if s.id not in exclude_set]

        # 按目的筛选
        if purpose:
            candidates = [s for s in candidates if purpose.lower() in " ".join(s.tags + [s.category, s.name]).lower()]

        # 必须包含
        must_include = set(include or [])
        must_skills = [s for s in candidates if s.id in must_include]
        optional_skills = [s for s in candidates if s.id not in must_include]

        # 贪心算法: 从 must 开始, 逐步添加评分最高的
        best_combination = must_skills[:]
        remaining = [s for s in optional_skills if s.id not in {ms.id for ms in must_skills}]

        while len(best_combination) < max_skills and remaining:
            best_candidate = None
            best_score = -1

            for candidate in remaining:
                trial = [s.id for s in best_combination] + [candidate.id]
                score_result = self.score_combination(trial)
                if not score_result.conflicts and score_result.score > best_score:
                    best_score = score_result.score
                    best_candidate = candidate

            if best_candidate:
                best_combination.append(best_candidate)
                remaining = [s for s in remaining if s.id != best_candidate.id]
            else:
                break

        # 最终评分
        final_ids = [s.id for s in best_combination]
        final_score = self.score_combination(final_ids)

        return {
            "recommended_skills": [
                {"id": s.id, "name": s.name, "category": s.category}
                for s in best_combination
            ],
            "combination_score": final_score.score,
            "conflicts": final_score.conflicts,
            "total_resource_cost": final_score.total_resource_cost,
            "synergy_score": final_score.synergy_score,
            "coverage_score": final_score.coverage_score,
        }

    # ----------------------------------------------------------
    # 统计
    # ----------------------------------------------------------

    def get_statistics(self) -> dict:
        skills = list(self._skills.values())
        categories = defaultdict(int)
        for s in skills:
            categories[s.category] += 1
        return {
            "total_skills": len(skills),
            "categories": dict(categories),
            "total_conflict_rules": len(self._conflict_rules),
        }


# 全局实例
_skill_combination_service: Optional[SkillCombinationService] = None


def get_skill_combination_service() -> SkillCombinationService:
    global _skill_combination_service
    if _skill_combination_service is None:
        _skill_combination_service = SkillCombinationService()
    return _skill_combination_service

"""
角色模板 Role-Master + Expertise Registry

功能:
- 预置角色模板（Leader/Expert/Reviewer/Coder/Researcher）
- 专长注册表（Agent→专长领域）
- 角色分配推荐
- 模板版本管理
- 跨 Agent 角色复用
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RoleTemplate:
    """角色模板"""
    id: str = ""
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    capabilities: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    required_mcp: list[str] = field(default_factory=list)
    recommended_model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    version: str = "1.0.0"
    created_at: Optional[datetime] = None


@dataclass
class ExpertiseEntry:
    """专长注册条目"""
    agent_id: str = ""
    agent_name: str = ""
    domains: list[str] = field(default_factory=list)   # 专长领域
    skills: list[str] = field(default_factory=list)     # 掌握技能
    experience_level: str = "intermediate"  # junior/intermediate/senior/expert
    max_concurrent: int = 5
    current_load: int = 0
    rating: float = 0.0  # 0-5 评分
    total_tasks: int = 0
    success_rate: float = 0.0
    registered_at: Optional[datetime] = None
    last_active: Optional[datetime] = None


class RoleMasterService:
    """
    角色模板 + 专长注册

    预置 5 大角色模板:
    1. Leader — 任务分解与协调
    2. Expert — 专业领域执行
    3. Reviewer — 质量审查
    4. Coder — 代码生成与调试
    5. Researcher — 信息检索与分析
    """

    def __init__(self):
        self._templates: dict[str, RoleTemplate] = {}
        self._registry: dict[str, ExpertiseEntry] = {}
        self._assignments: list[dict[str, Any]] = []
        self._setup_defaults()

    def _setup_defaults(self):
        """创建默认角色模板"""
        templates = [
            RoleTemplate(
                name="Leader",
                description="任务分解与协调者，负责将复杂任务分配给团队成员",
                system_prompt=(
                    "你是一个团队领导者。你的职责是：\n"
                    "1. 分解复杂任务为可执行的子任务\n"
                    "2. 根据团队成员专长分配任务\n"
                    "3. 协调进度和解决冲突\n"
                    "4. 汇总结果并生成报告"
                ),
                capabilities=["task_decomposition", "coordination", "summarization", "conflict_resolution"],
                required_skills=["task_management", "coordination"],
                recommended_model="gpt-4o",
                max_tokens=8192,
            ),
            RoleTemplate(
                name="Expert",
                description="专业领域执行者，在特定领域提供高质量输出",
                system_prompt=(
                    "你是一个专业领域的专家。你的职责是：\n"
                    "1. 根据分配的任务提供专业解答\n"
                    "2. 输出高质量、准确的结果\n"
                    "3. 如遇不确定，说明原因\n"
                    "4. 提供参考资料和依据"
                ),
                capabilities=["domain_expertise", "analysis", "problem_solving"],
                required_skills=["domain_knowledge"],
                recommended_model="gpt-4o",
            ),
            RoleTemplate(
                name="Reviewer",
                description="质量审查者，负责审查其他 Agent 的输出质量",
                system_prompt=(
                    "你是一个质量审查员。你的职责是：\n"
                    "1. 审查其他 Agent 的输出\n"
                    "2. 检查准确性、完整性和逻辑性\n"
                    "3. 提出改进建议\n"
                    "4. 给出质量评分"
                ),
                capabilities=["quality_review", "code_review", "feedback"],
                required_skills=["review", "analysis"],
                recommended_model="gpt-4o",
            ),
            RoleTemplate(
                name="Coder",
                description="代码生成与调试专家",
                system_prompt=(
                    "你是一个编程专家。你的职责是：\n"
                    "1. 根据需求生成高质量代码\n"
                    "2. 调试和修复代码问题\n"
                    "3. 编写测试用例\n"
                    "4. 优化代码性能"
                ),
                capabilities=["code_generation", "debugging", "testing", "optimization"],
                required_skills=["coding", "debugging"],
                recommended_model="gpt-4o",
            ),
            RoleTemplate(
                name="Researcher",
                description="信息检索与分析专家",
                system_prompt=(
                    "你是一个研究分析师。你的职责是：\n"
                    "1. 搜索和收集相关信息\n"
                    "2. 分析和评估信息质量\n"
                    "3. 整理结构化报告\n"
                    "4. 提供数据支持的建议"
                ),
                capabilities=["research", "data_analysis", "report_writing"],
                required_skills=["search", "analysis"],
                recommended_model="gpt-4o-mini",
            ),
        ]
        for t in templates:
            t.id = str(uuid.uuid4())
            t.created_at = datetime.now(timezone.utc)
            self._templates[t.id] = t

    # ----------------------------------------------------------
    # 模板管理
    # ----------------------------------------------------------

    def create_template(self, **kwargs) -> RoleTemplate:
        tpl = RoleTemplate(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            **kwargs,
        )
        self._templates[tpl.id] = tpl
        return tpl

    def update_template(self, template_id: str, **kwargs) -> bool:
        tpl = self._templates.get(template_id)
        if not tpl:
            return False
        for k, v in kwargs.items():
            if hasattr(tpl, k):
                setattr(tpl, k, v)
        return True

    def delete_template(self, template_id: str) -> bool:
        return self._templates.pop(template_id, None) is not None

    def get_template(self, template_id: str) -> Optional[dict[str, Any]]:
        tpl = self._templates.get(template_id)
        return self._tpl_to_dict(tpl) if tpl else None

    def list_templates(self) -> list[dict[str, Any]]:
        return [self._tpl_to_dict(t) for t in self._templates.values()]

    def get_template_by_name(self, name: str) -> Optional[RoleTemplate]:
        for t in self._templates.values():
            if t.name.lower() == name.lower():
                return t
        return None

    # ----------------------------------------------------------
    # 专长注册
    # ----------------------------------------------------------

    def register_expertise(
        self,
        agent_id: str,
        agent_name: str = "",
        domains: Optional[list[str]] = None,
        skills: Optional[list[str]] = None,
        experience_level: str = "intermediate",
        max_concurrent: int = 5,
    ) -> ExpertiseEntry:
        """注册 Agent 专长"""
        entry = ExpertiseEntry(
            agent_id=agent_id,
            agent_name=agent_name,
            domains=domains or [],
            skills=skills or [],
            experience_level=experience_level,
            max_concurrent=max_concurrent,
            registered_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        self._registry[agent_id] = entry
        return entry

    def update_expertise(self, agent_id: str, **kwargs) -> bool:
        entry = self._registry.get(agent_id)
        if not entry:
            return False
        for k, v in kwargs.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        entry.last_active = datetime.now(timezone.utc)
        return True

    def unregister(self, agent_id: str) -> bool:
        return self._registry.pop(agent_id, None) is not None

    def get_expertise(self, agent_id: str) -> Optional[dict[str, Any]]:
        entry = self._registry.get(agent_id)
        return self._entry_to_dict(entry) if entry else None

    def list_experts(self) -> list[dict[str, Any]]:
        return [self._entry_to_dict(e) for e in self._registry.values()]

    # ----------------------------------------------------------
    # 角色分配推荐
    # ----------------------------------------------------------

    def recommend_agents(
        self,
        required_domains: Optional[list[str]] = None,
        required_skills: Optional[list[str]] = None,
        role_name: str = "",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """推荐最适合的 Agent"""
        candidates = list(self._registry.values())

        # 过滤可用（负载未满）
        candidates = [e for e in candidates if e.current_load < e.max_concurrent]

        # 匹配打分
        scored = []
        for entry in candidates:
            score = 0
            if required_domains:
                domain_overlap = len(set(required_domains) & set(entry.domains))
                score += domain_overlap * 30

            if required_skills:
                skill_overlap = len(set(required_skills) & set(entry.skills))
                score += skill_overlap * 20

            # 经验等级加分
            level_scores = {"junior": 5, "intermediate": 10, "senior": 20, "expert": 30}
            score += level_scores.get(entry.experience_level, 10)

            # 评分加分
            score += entry.rating * 5

            # 成功率加分
            score += entry.success_rate * 10

            scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for entry, score in scored[:limit]:
            results.append({
                **self._entry_to_dict(entry),
                "match_score": round(score, 1),
            })
        return results

    def assign_role(
        self,
        agent_id: str,
        role_name: str,
        task_id: str = "",
    ) -> dict[str, Any]:
        """分配角色"""
        template = self.get_template_by_name(role_name)
        if not template:
            return {"error": f"Role template not found: {role_name}"}

        entry = self._registry.get(agent_id)
        if entry:
            entry.current_load += 1
            entry.last_active = datetime.now(timezone.utc)

        assignment = {
            "agent_id": agent_id,
            "role_name": role_name,
            "task_id": task_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._assignments.append(assignment)
        return assignment

    def release_role(self, agent_id: str) -> bool:
        entry = self._registry.get(agent_id)
        if entry and entry.current_load > 0:
            entry.current_load -= 1
            return True
        return False

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_assignments(self, agent_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        records = self._assignments
        if agent_id:
            records = [r for r in records if r["agent_id"] == agent_id]
        return records[-limit:]

    def get_domain_matrix(self) -> dict[str, list[str]]:
        """获取领域→Agent 映射矩阵"""
        matrix: dict[str, list[str]] = {}
        for entry in self._registry.values():
            for domain in entry.domains:
                if domain not in matrix:
                    matrix[domain] = []
                matrix[domain].append(entry.agent_id)
        return matrix

    @staticmethod
    def _tpl_to_dict(t: RoleTemplate) -> dict[str, Any]:
        return {
            "id": t.id, "name": t.name, "description": t.description,
            "capabilities": t.capabilities, "required_skills": t.required_skills,
            "recommended_model": t.recommended_model,
            "max_tokens": t.max_tokens, "temperature": t.temperature,
            "version": t.version,
        }

    @staticmethod
    def _entry_to_dict(e: ExpertiseEntry) -> dict[str, Any]:
        return {
            "agent_id": e.agent_id, "agent_name": e.agent_name,
            "domains": e.domains, "skills": e.skills,
            "experience_level": e.experience_level,
            "max_concurrent": e.max_concurrent, "current_load": e.current_load,
            "rating": e.rating, "total_tasks": e.total_tasks,
            "success_rate": e.success_rate,
        }

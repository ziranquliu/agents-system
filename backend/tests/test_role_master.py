"""
RoleMasterService 测试 — 角色模板、专长注册、分配推荐
"""
import pytest
from datetime import datetime, timezone

from app.services.role_master_service import (
    RoleMasterService,
    RoleTemplate,
    ExpertiseEntry,
)


# ============================================================
# RoleTemplate 测试
# ============================================================

class TestRoleTemplate:
    def test_default_template(self):
        tpl = RoleTemplate()
        assert tpl.name == ""
        assert tpl.version == "1.0.0"
        assert tpl.max_tokens == 4096
        assert tpl.temperature == 0.7


class TestExpertiseEntry:
    def test_default_entry(self):
        entry = ExpertiseEntry()
        assert entry.experience_level == "intermediate"
        assert entry.max_concurrent == 5
        assert entry.current_load == 0
        assert entry.rating == 0.0


# ============================================================
# RoleMasterService 模板管理测试
# ============================================================

class TestTemplateManagement:
    def setup_method(self):
        self.service = RoleMasterService()

    def test_default_templates_created(self):
        templates = self.service.list_templates()
        assert len(templates) == 5
        names = {t["name"] for t in templates}
        assert "Leader" in names
        assert "Expert" in names
        assert "Reviewer" in names
        assert "Coder" in names
        assert "Researcher" in names

    def test_create_template(self):
        tpl = self.service.create_template(name="Custom", description="Custom role")
        assert tpl.name == "Custom"
        assert tpl.id != ""
        assert len(self.service.list_templates()) == 6

    def test_update_template(self):
        templates = self.service.list_templates()
        tpl_id = templates[0]["id"]
        ok = self.service.update_template(tpl_id, name="Updated")
        assert ok is True
        updated = self.service.get_template(tpl_id)
        assert updated["name"] == "Updated"

    def test_update_nonexistent_template(self):
        assert self.service.update_template("nonexistent", name="X") is False

    def test_delete_template(self):
        templates = self.service.list_templates()
        tpl_id = templates[0]["id"]
        ok = self.service.delete_template(tpl_id)
        assert ok is True
        assert len(self.service.list_templates()) == 4

    def test_delete_nonexistent_template(self):
        assert self.service.delete_template("nonexistent") is False

    def test_get_template_by_name(self):
        tpl = self.service.get_template_by_name("leader")
        assert tpl is not None
        assert tpl.name == "Leader"

    def test_get_template_by_name_case_insensitive(self):
        tpl = self.service.get_template_by_name("EXPERT")
        assert tpl is not None

    def test_get_template_by_name_not_found(self):
        tpl = self.service.get_template_by_name("nonexistent")
        assert tpl is None


# ============================================================
# 专长注册测试
# ============================================================

class TestExpertiseRegistry:
    def setup_method(self):
        self.service = RoleMasterService()

    def test_register_expertise(self):
        entry = self.service.register_expertise(
            "a1", "Agent1",
            domains=["code", "data"],
            skills=["python", "sql"],
            experience_level="senior",
        )
        assert entry.agent_id == "a1"
        assert entry.domains == ["code", "data"]

    def test_list_experts(self):
        self.service.register_expertise("a1", "Agent1", domains=["code"])
        self.service.register_expertise("a2", "Agent2", domains=["data"])
        experts = self.service.list_experts()
        assert len(experts) == 2

    def test_get_expertise(self):
        self.service.register_expertise("a1", "Agent1")
        info = self.service.get_expertise("a1")
        assert info["agent_id"] == "a1"

    def test_get_expertise_not_found(self):
        assert self.service.get_expertise("nonexistent") is None

    def test_update_expertise(self):
        self.service.register_expertise("a1", "Agent1", domains=["code"])
        ok = self.service.update_expertise("a1", domains=["code", "ml"])
        assert ok is True
        info = self.service.get_expertise("a1")
        assert "ml" in info["domains"]

    def test_update_nonexistent_expertise(self):
        assert self.service.update_expertise("nonexistent") is False

    def test_unregister(self):
        self.service.register_expertise("a1", "Agent1")
        ok = self.service.unregister("a1")
        assert ok is True
        assert self.service.get_expertise("a1") is None

    def test_unregister_nonexistent(self):
        assert self.service.unregister("nonexistent") is False


# ============================================================
# 角色分配推荐测试
# ============================================================

class TestRecommendAgents:
    def setup_method(self):
        self.service = RoleMasterService()
        self.service.register_expertise(
            "a1", "CodeBot",
            domains=["code"],
            skills=["python"],
            experience_level="expert",
        )
        self.service.register_expertise(
            "a2", "DataBot",
            domains=["data"],
            skills=["sql"],
            experience_level="senior",
        )
        self.service.register_expertise(
            "a3", "FullStackBot",
            domains=["code", "data"],
            skills=["python", "sql"],
            experience_level="intermediate",
        )

    def test_recommend_by_domain(self):
        results = self.service.recommend_agents(required_domains=["code"])
        assert len(results) >= 1
        # a1 和 a3 有 code domain
        ids = {r["agent_id"] for r in results}
        assert "a1" in ids

    def test_recommend_by_skill(self):
        results = self.service.recommend_agents(required_skills=["python"])
        assert len(results) >= 1

    def test_recommend_sorted_by_score(self):
        results = self.service.recommend_agents(required_domains=["code"])
        scores = [r["match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_limit(self):
        results = self.service.recommend_agents(limit=1)
        assert len(results) == 1

    def test_recommend_no_matching_skills_gives_low_score(self):
        results = self.service.recommend_agents(required_skills=["nonexistent_skill_xyz"])
        # 不匹配的技能仍然返回（但分数较低）
        assert len(results) == 3
        # 所有分数应该只是基础经验等级分 + 评分分
        for r in results:
            assert r["match_score"] > 0  # 经验分保证最低分

    def test_recommend_excludes_full_load(self):
        self.service._registry["a1"].current_load = 5  # max_concurrent=5
        results = self.service.recommend_agents(required_domains=["code"])
        ids = {r["agent_id"] for r in results}
        assert "a1" not in ids


# ============================================================
# 角色分配测试
# ============================================================

class TestRoleAssignment:
    def setup_method(self):
        self.service = RoleMasterService()
        self.service.register_expertise("a1", "Agent1")

    def test_assign_role(self):
        result = self.service.assign_role("a1", "Coder", task_id="t1")
        assert result["agent_id"] == "a1"
        assert result["role_name"] == "Coder"
        assert result["task_id"] == "t1"

    def test_assign_role_increases_load(self):
        self.service.assign_role("a1", "Coder")
        info = self.service.get_expertise("a1")
        assert info["current_load"] == 1

    def test_assign_nonexistent_role(self):
        result = self.service.assign_role("a1", "NonexistentRole")
        assert "error" in result

    def test_assign_role_nonexistent_agent(self):
        result = self.service.assign_role("nonexistent", "Coder")
        assert "agent_id" in result  # still creates assignment record

    def test_release_role(self):
        self.service.assign_role("a1", "Coder")
        ok = self.service.release_role("a1")
        assert ok is True
        info = self.service.get_expertise("a1")
        assert info["current_load"] == 0

    def test_release_role_empty_load(self):
        ok = self.service.release_role("a1")
        assert ok is False

    def test_assignments_history(self):
        self.service.assign_role("a1", "Coder", task_id="t1")
        self.service.assign_role("a1", "Reviewer", task_id="t2")
        assert len(self.service._assignments) == 2

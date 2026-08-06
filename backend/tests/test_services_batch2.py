"""
测试 - 技能组合优化服务
"""

import pytest


class TestSkillCombination:
    """技能组合优化"""

    def _make_service(self):
        from app.services.skill_combination_service import SkillCombinationService
        return SkillCombinationService()

    def test_register_skill(self):
        svc = self._make_service()
        result = svc.register_skill({
            "id": "s1", "name": "代码分析", "category": "code",
            "tags": ["python", "review"], "dependencies": [],
            "conflicts": ["s2"], "resource_cost": 1.5,
        })
        assert result["registered"] is True

    def test_list_skills(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "category": "code"})
        svc.register_skill({"id": "s2", "name": "B", "category": "search"})
        skills = svc.list_skills()
        assert len(skills) == 2

    def test_detect_conflicts(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "conflicts": ["s2"]})
        svc.register_skill({"id": "s2", "name": "B", "conflicts": ["s1"]})
        conflicts = svc.detect_conflicts(["s1", "s2"])
        assert len(conflicts) >= 1

    def test_no_conflicts(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A"})
        svc.register_skill({"id": "s2", "name": "B"})
        conflicts = svc.detect_conflicts(["s1", "s2"])
        assert len(conflicts) == 0

    def test_check_dependencies_met(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "dependencies": []})
        result = svc.check_dependencies(["s1"])
        assert result["all_satisfied"] is True

    def test_check_dependencies_missing(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "dependencies": ["s2"]})
        result = svc.check_dependencies(["s1"])
        assert result["all_satisfied"] is False
        assert len(result["missing"]) == 1

    def test_score_combination(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "category": "code", "tags": ["python"]})
        svc.register_skill({"id": "s2", "name": "B", "category": "search", "tags": ["text"]})
        result = svc.score_combination(["s1", "s2"])
        assert 0 <= result.score <= 100
        assert len(result.conflicts) == 0

    def test_score_with_conflicts(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "conflicts": ["s2"]})
        svc.register_skill({"id": "s2", "name": "B", "conflicts": ["s1"]})
        result = svc.score_combination(["s1", "s2"])
        assert result.score < 80  # 冲突扣分

    def test_recommend(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "Python分析", "category": "code", "tags": ["python"]})
        svc.register_skill({"id": "s2", "name": "文本搜索", "category": "search", "tags": ["text"]})
        svc.register_skill({"id": "s3", "name": "数据库", "category": "db", "tags": ["sql"]})
        result = svc.recommend(purpose="python", max_skills=2)
        assert len(result["recommended_skills"]) <= 2

    def test_statistics(self):
        svc = self._make_service()
        svc.register_skill({"id": "s1", "name": "A", "category": "code"})
        stats = svc.get_statistics()
        assert stats["total_skills"] == 1


class TestModelBenchmark:
    """模型基准评测"""

    def _make_service(self):
        from app.services.model_benchmark_service import ModelBenchmarkService
        return ModelBenchmarkService()

    def test_run_benchmark(self):
        svc = self._make_service()
        result = svc.run_benchmark("gpt-4o")
        assert result["total_tasks"] > 0
        assert result["composite_score"] > 0

    def test_leaderboard(self):
        svc = self._make_service()
        svc.run_benchmark("gpt-4o")
        svc.run_benchmark("claude-3.5-sonnet")
        lb = svc.leaderboard()
        assert len(lb) == 2
        assert lb[0]["rank"] == 1

    def test_compare(self):
        svc = self._make_service()
        svc.run_benchmark("gpt-4o")
        svc.run_benchmark("gpt-4o-mini")
        result = svc.compare(["gpt-4o", "gpt-4o-mini"])
        assert len(result["models"]) == 2

    def test_report(self):
        svc = self._make_service()
        svc.run_benchmark("deepseek-v3")
        report = svc.get_report("deepseek-v3")
        assert report is not None
        assert report["composite_score"] > 0

    def test_list_tasks(self):
        svc = self._make_service()
        tasks = svc.list_tasks()
        assert len(tasks) == 10  # 默认 10 个评测任务

    def test_add_custom_task(self):
        svc = self._make_service()
        result = svc.add_task({
            "id": "custom1",
            "prompt": "自定义任务",
            "expected_output": "expected",
            "category": "general",
        })
        assert result["added"] is True
        assert len(svc.list_tasks()) == 11


class TestDashboard:
    """自定义仪表盘"""

    def _make_service(self):
        from app.services.dashboard_service import DashboardService
        return DashboardService()

    def test_create_dashboard(self):
        svc = self._make_service()
        result = svc.create_dashboard("测试面板", "user1")
        assert "dash_" in result["id"]

    def test_create_with_template(self):
        svc = self._make_service()
        result = svc.create_dashboard("系统概览", "user1", template_id="tpl_overview")
        d = svc.get_dashboard(result["id"])
        assert len(d["widgets"]) > 0

    def test_add_widget(self):
        svc = self._make_service()
        d = svc.create_dashboard("测试", "user1")
        result = svc.add_widget(d["id"], {"widget_type": "metric", "title": "请求数"})
        assert result["added"] is True

    def test_list_templates(self):
        svc = self._make_service()
        templates = svc.list_templates()
        assert len(templates) == 3  # 预设 3 个模板

    def test_sharing(self):
        svc = self._make_service()
        d = svc.create_dashboard("共享测试", "user1")
        svc.share_dashboard(d["id"], ["user2", "user3"])
        assert svc.can_access(d["id"], "user2") is True
        assert svc.can_access(d["id"], "stranger") is False

    def test_delete_dashboard(self):
        svc = self._make_service()
        d = svc.create_dashboard("要删除", "user1")
        result = svc.delete_dashboard(d["id"])
        assert result["deleted"] is True

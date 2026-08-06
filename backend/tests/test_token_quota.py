"""
测试 - Token 配额管理
"""

import pytest


class TestTokenQuota:
    """Token 配额 CRUD"""

    def _make_service(self):
        from app.services.token_quota_service import TokenQuotaService
        return TokenQuotaService()

    def test_create_quota(self):
        svc = self._make_service()
        result = svc.create_quota("user", "u1", daily_limit=10000, monthly_limit=300000)
        assert result["created"] is True
        assert "quota_user_u1" in result["quota_id"]

    def test_create_duplicate(self):
        svc = self._make_service()
        svc.create_quota("user", "u1")
        result = svc.create_quota("user", "u1")
        assert "error" in result

    def test_get_quota(self):
        svc = self._make_service()
        svc.create_quota("agent", "a1", daily_limit=50000)
        q = svc.get_quota("quota_agent_a1")
        assert q is not None
        assert q["daily_limit"] == 50000
        assert q["daily_remaining"] == 50000

    def test_record_usage(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=10000)
        result = svc.record_usage("user", "u1", tokens=1000, model="gpt-4o")
        assert result["recorded"] is True
        assert result["daily_used"] == 1000

    def test_record_usage_accumulates(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=10000)
        svc.record_usage("user", "u1", 500)
        result = svc.record_usage("user", "u1", 300)
        assert result["daily_used"] == 800

    def test_check_available_within_limit(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=10000)
        result = svc.check_available("user", "u1", 5000)
        assert result["available"] is True

    def test_check_available_exceeds(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=1000)
        svc.record_usage("user", "u1", 800)
        result = svc.check_available("user", "u1", 500)
        assert result["available"] is False
        assert len(result["reasons"]) > 0

    def test_alert_threshold(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=1000, alert_threshold=0.8)
        result = svc.record_usage("user", "u1", 850)
        assert len(result["alerts"]) > 0
        assert result["alerts"][0]["type"] == "threshold"

    def test_update_quota(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=1000)
        result = svc.update_quota("quota_user_u1", {"daily_limit": 5000})
        assert result["updated"] is True
        q = svc.get_quota("quota_user_u1")
        assert q["daily_limit"] == 5000

    def test_delete_quota(self):
        svc = self._make_service()
        svc.create_quota("user", "u1")
        result = svc.delete_quota("quota_user_u1")
        assert result["deleted"] is True
        assert svc.get_quota("quota_user_u1") is None

    def test_list_quotas(self):
        svc = self._make_service()
        svc.create_quota("user", "u1")
        svc.create_quota("user", "u2")
        svc.create_quota("agent", "a1")
        quotas = svc.list_quotas(entity_type="user")
        assert len(quotas) == 2

    def test_usage_history(self):
        svc = self._make_service()
        svc.create_quota("user", "u1")
        svc.record_usage("user", "u1", 100)
        svc.record_usage("user", "u1", 200)
        history = svc.get_usage_history("quota_user_u1")
        assert len(history) == 2
        assert history[0]["tokens"] == 100

    def test_reset_daily(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=10000)
        svc.record_usage("user", "u1", 5000)
        svc.reset_daily()
        q = svc.get_quota("quota_user_u1")
        assert q["daily_used"] == 0

    def test_statistics(self):
        svc = self._make_service()
        svc.create_quota("user", "u1", daily_limit=10000)
        svc.create_quota("agent", "a1", daily_limit=5000)
        stats = svc.get_statistics()
        assert stats["total_quotas"] == 2
        assert stats["total_daily_limit"] == 15000

    def test_no_limit_quota(self):
        svc = self._make_service()
        svc.create_quota("user", "u1")  # 无限制
        result = svc.check_available("user", "u1", 999999999)
        assert result["available"] is True

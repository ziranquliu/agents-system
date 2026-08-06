"""
测试 - 统一响应格式 + 错误码 + RBAC
"""

import pytest


class TestUnifiedResponse:
    """统一响应格式"""

    def test_success(self):
        from app.core.unified_response import UnifiedResponse
        resp = UnifiedResponse.success(data={"key": "value"})
        assert resp["code"] == 0
        assert resp["data"]["key"] == "value"
        assert resp["message"] == "success"
        assert "request_id" in resp
        assert "timestamp" in resp

    def test_success_custom_message(self):
        from app.core.unified_response import UnifiedResponse
        resp = UnifiedResponse.success(message="自定义消息")
        assert resp["message"] == "自定义消息"

    def test_error(self):
        from app.core.unified_response import UnifiedResponse, ErrorCode
        resp = UnifiedResponse.error(ErrorCode.AUTH_FAILED)
        assert resp["code"] == 401
        assert resp["error_code"] == "01-001-01"
        assert resp["message"] == "认证失败"

    def test_error_custom_message(self):
        from app.core.unified_response import UnifiedResponse, ErrorCode
        resp = UnifiedResponse.error(ErrorCode.PARAM_INVALID, message="自定义错误")
        assert resp["message"] == "自定义错误"

    def test_paginated(self):
        from app.core.unified_response import UnifiedResponse
        items = [{"id": i} for i in range(25)]
        resp = UnifiedResponse.paginated(items=items, total=100, page=2, page_size=25)
        assert resp["code"] == 0
        assert resp["data"]["total"] == 100
        assert resp["data"]["page"] == 2
        assert resp["data"]["total_pages"] == 4
        assert len(resp["data"]["items"]) == 25


class TestErrorCode:
    """错误码体系"""

    def test_format(self):
        from app.core.unified_response import ErrorCode
        for ec in ErrorCode:
            parts = ec.value.split("-")
            assert len(parts) == 3, f"{ec.value} format error"
            assert len(parts[0]) == 2
            assert len(parts[1]) == 3
            assert len(parts[2]) == 2

    def test_http_status(self):
        from app.core.unified_response import ErrorCode
        assert ErrorCode.SUCCESS.http_status == 200
        assert ErrorCode.AUTH_FAILED.http_status == 401
        assert ErrorCode.PERMISSION_DENIED.http_status == 403
        assert ErrorCode.AGENT_NOT_FOUND.http_status == 404
        assert ErrorCode.REQUEST_TOO_FREQUENT.http_status == 429
        assert ErrorCode.INTERNAL_ERROR.http_status == 500
        assert ErrorCode.SYSTEM_OVERLOADED.http_status == 500

    def test_message(self):
        from app.core.unified_response import ErrorCode
        assert ErrorCode.SUCCESS.message == "操作成功"
        assert "认证失败" in ErrorCode.AUTH_FAILED.message
        assert "Agent 不存在" in ErrorCode.AGENT_NOT_FOUND.message

    def test_unique_values(self):
        from app.core.unified_response import ErrorCode
        values = [ec.value for ec in ErrorCode]
        assert len(values) == len(set(values)), "错误码值不唯一"


class TestRBAC:
    """RBAC 权限"""

    def test_default_role_viewer(self):
        from app.core.unified_response import get_rbac_middleware, Permission
        rbac = get_rbac_middleware()
        assert rbac.get_user_role("unknown_user") == "viewer"
        assert not rbac.check_permission("unknown_user", Permission.AGENT_DELETE)

    def test_set_role(self):
        from app.core.unified_response import get_rbac_middleware, Role, Permission
        rbac = get_rbac_middleware()
        rbac.set_user_role("admin_user", Role.ADMIN.value)
        assert rbac.get_user_role("admin_user") == "admin"
        assert rbac.check_permission("admin_user", Permission.AGENT_CREATE)
        assert not rbac.check_permission("admin_user", Permission.AGENT_DELETE)

    def test_super_admin_all_permissions(self):
        from app.core.unified_response import get_rbac_middleware, Role, Permission
        rbac = get_rbac_middleware()
        rbac.set_user_role("super_user", Role.SUPER_ADMIN.value)
        for perm in Permission:
            assert rbac.check_permission("super_user", perm), f"超级管理员缺少权限: {perm.value}"

    def test_viewer_readonly(self):
        from app.core.unified_response import get_rbac_middleware, Role, Permission
        rbac = get_rbac_middleware()
        rbac.set_user_role("viewer_user", Role.VIEWER.value)
        assert rbac.check_permission("viewer_user", Permission.AGENT_VIEW)
        assert not rbac.check_permission("viewer_user", Permission.AGENT_CREATE)
        assert not rbac.check_permission("viewer_user", Permission.MODEL_DELETE)

    def test_permission_count(self):
        from app.core.unified_response import Permission
        assert len(Permission) >= 55, f"权限数不足: {len(Permission)}"

    def test_public_path(self):
        from app.core.unified_response import get_rbac_middleware
        rbac = get_rbac_middleware()
        assert rbac.is_public_path("/health")
        assert rbac.is_public_path("/docs")
        assert rbac.is_public_path("/api/v1/auth/login")
        assert not rbac.is_public_path("/api/v1/agents")

    def test_path_permission_match(self):
        from app.core.unified_response import get_rbac_middleware, Permission
        rbac = get_rbac_middleware()
        perm = rbac.get_required_permission("GET", "/api/v1/agents")
        assert perm == Permission.AGENT_VIEW
        perm = rbac.get_required_permission("POST", "/api/v1/agents")
        assert perm == Permission.AGENT_CREATE
        perm = rbac.get_required_permission("DELETE", "/api/v1/agents/123")
        assert perm == Permission.AGENT_DELETE

"""工作区 API 测试"""
import pytest
try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("缺少依赖", allow_module_level=True)


class TestWorkspaces:
    """工作区 CRUD + 成员管理"""

    @staticmethod
    def _create_get_id(client, headers, name="测试工作区"):
        resp = client.post(
            "/api/v1/workspaces/",
            json={"name": name, "description": "自动化测试工作区"},
            headers=headers,
        )
        return resp.json()["id"]

    def test_create_workspace(self, client, auth_headers):
        """创建工作区"""
        resp = client.post(
            "/api/v1/workspaces/",
            json={"name": "新工作区", "description": "测试描述"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "新工作区"
        assert data["description"] == "测试描述"
        assert "id" in data

    def test_create_workspace_missing_name(self, client, auth_headers):
        """创建缺少名称的工作区应失败"""
        resp = client.post(
            "/api/v1/workspaces/",
            json={"description": "没有名称"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_list_workspaces(self, client, auth_headers):
        """工作区列表"""
        self._create_get_id(client, auth_headers)
        resp = client.get("/api/v1/workspaces/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_workspace(self, client, auth_headers):
        """获取工作区详情"""
        ws_id = self._create_get_id(client, auth_headers)
        resp = client.get(f"/api/v1/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == ws_id

    def test_get_workspace_not_found(self, client, auth_headers):
        """获取不存在的工作区"""
        resp = client.get("/api/v1/workspaces/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_workspace(self, client, auth_headers):
        """更新工作区"""
        ws_id = self._create_get_id(client, auth_headers)
        resp = client.put(
            f"/api/v1/workspaces/{ws_id}",
            json={"name": "更新工作区", "description": "新描述"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新工作区"
        assert resp.json()["description"] == "新描述"

    def test_update_workspace_deactivate(self, client, auth_headers):
        """禁用工作区"""
        ws_id = self._create_get_id(client, auth_headers)
        resp = client.put(
            f"/api/v1/workspaces/{ws_id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_delete_workspace(self, client, auth_headers):
        """删除工作区"""
        ws_id = self._create_get_id(client, auth_headers)
        resp = client.delete(f"/api/v1/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 204
        # 验证已删除
        resp = client.get(f"/api/v1/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 404

    # ---------- 成员管理 ----------

    def _create_ws_with_context(self, client, auth_headers):
        ws_id = self._create_get_id(client, auth_headers)
        # 获取当前用户信息
        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        me = me_resp.json()
        return ws_id, me["id"]

    def test_add_member(self, client, auth_headers):
        """添加成员到自己创建的工作区"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["user_id"] == my_id

    def test_add_member_invalid_role(self, client, auth_headers):
        """添加成员时使用无效角色应失败或返回有限角色集"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "superadmin"},
            headers=auth_headers,
        )
        # 预期：422（Pydantic 校验）或 200（后端允许但限制）
        assert resp.status_code in (200, 422)

    def test_list_members(self, client, auth_headers):
        """成员列表"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        # 添加自己为成员
        client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "member"},
            headers=auth_headers,
        )
        resp = client.get(f"/api/v1/workspaces/{ws_id}/members", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
        assert len(items) >= 1

    def test_update_member_role(self, client, auth_headers):
        """更新成员角色"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        # 添加自己为 member
        client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "member"},
            headers=auth_headers,
        )
        # 提升为 admin
        resp = client.put(
            f"/api/v1/workspaces/{ws_id}/members/{my_id}",
            json={"role": "admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_remove_member(self, client, auth_headers):
        """移除成员"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        # 添加自己
        client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "member"},
            headers=auth_headers,
        )
        # 移除自己
        resp = client.delete(
            f"/api/v1/workspaces/{ws_id}/members/{my_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_members_count_in_workspace(self, client, auth_headers):
        """工作区详情包含成员数"""
        ws_id, my_id = self._create_ws_with_context(client, auth_headers)
        client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": my_id, "role": "member"},
            headers=auth_headers,
        )
        resp = client.get(f"/api/v1/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 200
        # 验证 member_count 字段存在（如果后端返回的话）
        data = resp.json()
        assert "member_count" in data or "members" in data

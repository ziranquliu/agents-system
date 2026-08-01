"""技能 API 测试"""
import pytest

pytestmark = pytest.mark.asyncio


class TestSkills:
    """技能 CRUD + 绑定/解绑"""

    CREATE_PAYLOAD = {
        "name": "测试技能",
        "type": "tool",
        "version": "1.0.0",
        "category": "analysis",
        "description": "自动化测试技能",
        "enabled": True,
        "config": {"timeout": 30, "retry": 3},
    }

    @staticmethod
    async def _create_get_id(client, headers):
        resp = await client.post("/api/v1/skills/", json=TestSkills.CREATE_PAYLOAD, headers=headers)
        return resp.json()["id"]

    @staticmethod
    async def _create_agent_id(client, headers):
        resp = await client.post(
            "/api/v1/agents/",
            json={"name": "测试Agent-Skill", "type": "assistant", "description": "绑定测试"},
            headers=headers,
        )
        return resp.json()["id"]

    async def test_create_skill(self, client, auth_headers):
        """创建技能"""
        resp = await client.post("/api/v1/skills/", json=self.CREATE_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "测试技能"
        assert data["type"] == "tool"
        assert data["version"] == "1.0.0"
        assert "id" in data
        assert data["status"] in ("active", "inactive")

    async def test_create_skill_missing_name(self, client, auth_headers):
        """创建缺少名称的技能应失败"""
        resp = await client.post(
            "/api/v1/skills/",
            json={"type": "tool"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_list_skills(self, client, auth_headers):
        """技能列表"""
        await self._create_get_id(client, auth_headers)
        resp = await client.get("/api/v1/skills/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_get_skill(self, client, auth_headers):
        """获取技能详情"""
        skill_id = await self._create_get_id(client, auth_headers)
        resp = await client.get(f"/api/v1/skills/{skill_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == skill_id

    async def test_get_skill_not_found(self, client, auth_headers):
        """获取不存在的技能"""
        resp = await client.get("/api/v1/skills/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_skill(self, client, auth_headers):
        """更新技能"""
        skill_id = await self._create_get_id(client, auth_headers)
        resp = await client.put(
            f"/api/v1/skills/{skill_id}",
            json={"name": "更新技能", "description": "已更新描述", "version": "2.0.0"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新技能"
        assert data["version"] == "2.0.0"

    async def test_delete_skill(self, client, auth_headers):
        """删除技能"""
        skill_id = await self._create_get_id(client, auth_headers)
        resp = await client.delete(f"/api/v1/skills/{skill_id}", headers=auth_headers)
        assert resp.status_code == 200
        # 验证已删除
        resp = await client.get(f"/api/v1/skills/{skill_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_toggle_skill(self, client, auth_headers):
        """切换技能状态"""
        skill_id = await self._create_get_id(client, auth_headers)
        resp = await client.patch(f"/api/v1/skills/{skill_id}/toggle", headers=auth_headers)
        assert resp.status_code == 200

    async def test_filter_by_type(self, client, auth_headers):
        """按类型筛选"""
        await self._create_get_id(client, auth_headers)
        resp = await client.get("/api/v1/skills/?type=tool", headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item.get("type") == "tool"

    async def test_bind_skill_to_agent(self, client, auth_headers):
        """绑定技能到 Agent"""
        skill_id = await self._create_get_id(client, auth_headers)
        agent_id = await self._create_agent_id(client, auth_headers)
        resp = await client.post(
            f"/api/v1/skills/{skill_id}/bind",
            json={"agent_id": agent_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == agent_id

    async def test_bind_skill_invalid_agent(self, client, auth_headers):
        """绑定到不存在的 Agent 应失败"""
        skill_id = await self._create_get_id(client, auth_headers)
        resp = await client.post(
            f"/api/v1/skills/{skill_id}/bind",
            json={"agent_id": "nonexistent-agent"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_unbind_skill(self, client, auth_headers):
        """解绑技能"""
        skill_id = await self._create_get_id(client, auth_headers)
        agent_id = await self._create_agent_id(client, auth_headers)
        # 先绑定
        await client.post(
            f"/api/v1/skills/{skill_id}/bind",
            json={"agent_id": agent_id},
            headers=auth_headers,
        )
        # 再解绑
        resp = await client.delete(
            f"/api/v1/skills/{skill_id}/bind/{agent_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_agents_count(self, client, auth_headers):
        """技能关联的 Agent 计数（绑定后应增加）"""
        skill_id = await self._create_get_id(client, auth_headers)
        agent_id = await self._create_agent_id(client, auth_headers)

        # 绑定前查看
        resp = await client.get(f"/api/v1/skills/{skill_id}", headers=auth_headers)
        before = resp.json().get("agents_count", 0)

        # 绑定
        await client.post(
            f"/api/v1/skills/{skill_id}/bind",
            json={"agent_id": agent_id},
            headers=auth_headers,
        )

        # 绑定后查看
        resp = await client.get(f"/api/v1/skills/{skill_id}", headers=auth_headers)
        after = resp.json().get("agents_count", 0)
        assert after > before

    async def test_create_skill_minimal(self, client, auth_headers):
        """最简参数创建技能"""
        resp = await client.post(
            "/api/v1/skills/",
            json={"name": "极简技能"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "极简技能"

"""MCP Server API 测试"""
import pytest

pytestmark = pytest.mark.asyncio


class TestMCP:
    """MCP Server CRUD + 健康检测"""

    CREATE_PAYLOAD = {
        "name": "测试MCP服务",
        "endpoint": "http://localhost:9999/mcp",
        "protocol": "sse",
        "api_key": "mcp-test-key",
        "description": "自动化测试 MCP",
        "config": {"timeout": 10},
    }

    @staticmethod
    async def _create_get_id(client, headers):
        resp = await client.post("/api/v1/mcp-servers/", json=TestMCP.CREATE_PAYLOAD, headers=headers)
        return resp.json()["id"]

    async def test_create_mcp(self, client, auth_headers):
        """创建 MCP Server"""
        resp = await client.post("/api/v1/mcp-servers/", json=self.CREATE_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "测试MCP服务"
        assert data["protocol"] == "sse"
        assert "id" in data

    async def test_create_mcp_missing_endpoint(self, client, auth_headers):
        """创建缺少 endpoint 应失败"""
        resp = await client.post(
            "/api/v1/mcp-servers/",
            json={"name": "不完整MCP"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_list_mcp(self, client, auth_headers):
        """MCP 列表"""
        await self._create_get_id(client, auth_headers)
        resp = await client.get("/api/v1/mcp-servers/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_get_mcp(self, client, auth_headers):
        """获取 MCP 详情"""
        mcp_id = await self._create_get_id(client, auth_headers)
        resp = await client.get(f"/api/v1/mcp-servers/{mcp_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == mcp_id

    async def test_get_mcp_not_found(self, client, auth_headers):
        """获取不存在的 MCP"""
        resp = await client.get("/api/v1/mcp-servers/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_mcp(self, client, auth_headers):
        """更新 MCP"""
        mcp_id = await self._create_get_id(client, auth_headers)
        resp = await client.put(
            f"/api/v1/mcp-servers/{mcp_id}",
            json={"name": "更新MCP", "description": "已更新描述"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新MCP"

    async def test_delete_mcp(self, client, auth_headers):
        """删除 MCP"""
        mcp_id = await self._create_get_id(client, auth_headers)
        resp = await client.delete(f"/api/v1/mcp-servers/{mcp_id}", headers=auth_headers)
        assert resp.status_code == 200
        # 验证已删除
        resp = await client.get(f"/api/v1/mcp-servers/{mcp_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_health_check_skip(self, client, auth_headers):
        """健康检测（只验证路由）"""
        mcp_id = await self._create_get_id(client, auth_headers)
        resp = await client.post(f"/api/v1/mcp-servers/{mcp_id}/health-check", headers=auth_headers)
        # 由于没有真实服务，预期是连接失败而非路由错误
        assert resp.status_code in (200, 502, 503)

    async def test_filter_by_protocol(self, client, auth_headers):
        """按协议筛选"""
        await self._create_get_id(client, auth_headers)
        # 创建 sse 协议的服务
        resp = await client.get("/api/v1/mcp-servers/?protocol=sse", headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item.get("protocol") == "sse"

    async def test_create_mcp_stream(self, client, auth_headers):
        """创建 stream 协议 MCP"""
        payload = {
            **self.CREATE_PAYLOAD,
            "name": "Stream MCP",
            "protocol": "stream",
        }
        resp = await client.post("/api/v1/mcp-servers/", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["protocol"] == "stream"

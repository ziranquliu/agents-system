"""模型配置 API 测试"""
import pytest

pytestmark = pytest.mark.asyncio


class TestModels:
    """模型配置 CRUD + 测试连接"""

    CREATE_PAYLOAD = {
        "name": "测试模型-GPT",
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "endpoint": "https://api.openai.com/v1",
        "api_key": "sk-test-key-12345",
        "temperature": 0.7,
        "max_tokens": 4096,
        "context_window": 128000,
        "embedding_model": "text-embedding-3-small",
        "is_default": False,
        "description": "自动化测试创建的模型",
    }

    async def test_create_model(self, client, auth_headers):
        """创建模型配置"""
        resp = await client.post("/api/v1/models/", json=self.CREATE_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == self.CREATE_PAYLOAD["name"]
        assert data["provider"] == "openai"
        assert data["model_name"] == "gpt-4o-mini"
        assert "id" in data
        assert "api_key_masked" in data
        # API key 应脱敏
        assert data["api_key_masked"] != self.CREATE_PAYLOAD["api_key"]

    async def test_create_model_duplicate(self, client, auth_headers):
        """创建同名模型应失败"""
        await client.post("/api/v1/models/", json=self.CREATE_PAYLOAD, headers=auth_headers)
        resp = await client.post("/api/v1/models/", json=self.CREATE_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 409

    async def test_list_models(self, client, auth_headers):
        """模型列表"""
        model_id = await self._create_get_id(client, auth_headers)
        resp = await client.get("/api/v1/models/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        ids = [item["id"] for item in data["items"]]
        assert model_id in ids

    async def test_get_model(self, client, auth_headers):
        """获取模型详情"""
        model_id = await self._create_get_id(client, auth_headers)
        resp = await client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == model_id

    async def test_get_model_not_found(self, client, auth_headers):
        """获取不存在的模型"""
        resp = await client.get("/api/v1/models/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_model(self, client, auth_headers):
        """更新模型配置"""
        model_id = await self._create_get_id(client, auth_headers)
        resp = await client.put(
            f"/api/v1/models/{model_id}",
            json={"name": "更新后的模型", "temperature": 0.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新后的模型"
        assert data["temperature"] == 0.5

    async def test_delete_model(self, client, auth_headers):
        """删除模型"""
        model_id = await self._create_get_id(client, auth_headers)
        resp = await client.delete(f"/api/v1/models/{model_id}", headers=auth_headers)
        assert resp.status_code == 200
        # 验证已删除
        resp = await client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_test_connection_skip(self, client, auth_headers):
        """测试连接（只验证路由可达，不期待真实连接）"""
        model_id = await self._create_get_id(client, auth_headers)
        resp = await client.post(
            f"/api/v1/models/{model_id}/test",
            json={"messages": [{"role": "user", "content": "Say hello"}]},
            headers=auth_headers,
        )
        # 由于没有真实 API key，预期返回连接失败而非路由错误
        assert resp.status_code in (200, 502, 503)

    async def test_pagination(self, client, auth_headers):
        """分页参数"""
        resp = await client.get("/api/v1/models/?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    async def test_create_model_with_default(self, client, auth_headers):
        """创建默认模型"""
        payload = {**self.CREATE_PAYLOAD, "name": "默认模型", "is_default": True}
        resp = await client.post("/api/v1/models/", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    # ---------- helpers ----------

    @staticmethod
    async def _create_get_id(client, headers):
        resp = await client.post("/api/v1/models/", json=TestModels.CREATE_PAYLOAD, headers=headers)
        return resp.json()["id"]

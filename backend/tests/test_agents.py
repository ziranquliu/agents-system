"""Agent API 测试"""
import pytest


class TestAgents:
    """Agent 管理相关测试"""
    def test_list_agents_empty(self, client, auth_headers):
        """初始时 Agent 列表为空"""
        resp = client.get("/api/v1/agents/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1
    def test_create_agent(self, client, auth_headers):
        """创建 Agent"""
        resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "测试助手",
            "description": "一个用于测试的 Agent",
            "system_prompt": "你是一个测试助手",
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 4096,
        })
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "测试助手"
        assert data["status"] == "draft"
        assert "id" in data
        assert data["created_by"] is not None
        return data["id"]
    def test_create_agent_minimal(self, client, auth_headers):
        """创建 Agent（仅必填字段）"""
        resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "最小化Agent",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "最小化Agent"
        assert data["status"] == "draft"
    def test_get_agent(self, client, auth_headers):
        """获取 Agent 详情"""
        # 先创建
        create_resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "获取测试Agent",
        })
        agent_id = create_resp.json()["id"]

        # 获取详情
        resp = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "获取测试Agent"
        assert data["id"] == agent_id
    def test_get_agent_not_found(self, client, auth_headers):
        """不存在的 Agent 应 404"""
        resp = client.get("/api/v1/agents/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404
    def test_update_agent(self, client, auth_headers):
        """更新 Agent"""
        # 先创建
        create_resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "更新前名称",
        })
        agent_id = create_resp.json()["id"]

        # 更新
        resp = client.put(f"/api/v1/agents/{agent_id}", headers=auth_headers, json={
            "name": "更新后名称",
            "description": "更新后的描述",
            "temperature": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新后名称"
        assert data["description"] == "更新后的描述"
        assert data["temperature"] == 0.5
    def test_delete_agent(self, client, auth_headers):
        """删除 Agent"""
        # 先创建
        create_resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "待删除Agent",
        })
        agent_id = create_resp.json()["id"]

        # 删除
        resp = client.delete(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 204

        # 确认已删除
        resp = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 404
    def test_update_agent_status(self, client, auth_headers):
        """状态变更"""
        # 先创建 (默认 draft)
        create_resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "状态测试Agent",
        })
        agent_id = create_resp.json()["id"]

        # draft -> running
        resp = client.patch(
            f"/api/v1/agents/{agent_id}/status",
            headers=auth_headers,
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        # running -> stopped
        resp = client.patch(
            f"/api/v1/agents/{agent_id}/status",
            headers=auth_headers,
            json={"status": "stopped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

        # stopped -> archived
        resp = client.patch(
            f"/api/v1/agents/{agent_id}/status",
            headers=auth_headers,
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
    def test_invalid_status_transition(self, client, auth_headers):
        """非法状态转换应 400"""
        # 创建 (draft)
        create_resp = client.post("/api/v1/agents/", headers=auth_headers, json={
            "name": "非法状态测试",
        })
        agent_id = create_resp.json()["id"]

        # draft 不能直接到 archived
        resp = client.patch(
            f"/api/v1/agents/{agent_id}/status",
            headers=auth_headers,
            json={"status": "archived"},
        )
        assert resp.status_code == 400
    def test_list_agents_with_search(self, client, auth_headers):
        """搜索 Agent"""
        # 创建两个 Agent
        client.post("/api/v1/agents/", headers=auth_headers, json={"name": "Alpha Bot"})
        client.post("/api/v1/agents/", headers=auth_headers, json={"name": "Beta Bot"})

        # 搜索 "Alpha"
        resp = client.get("/api/v1/agents/?search=Alpha", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all("Alpha" in a["name"] for a in data["items"])
    def test_list_agents_with_pagination(self, client, auth_headers):
        """分页"""
        resp = client.get("/api/v1/agents/?page=1&page_size=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2
    def test_create_agent_unauthorized(self, client):
        """未认证创建 Agent 应 401"""
        resp = client.post("/api/v1/agents/", json={"name": "unauthorized"})
        assert resp.status_code == 401

"""对话和消息 API 测试"""
import pytest


class TestConversations:
    """对话 CRUD + 消息管理"""

    @staticmethod
    def _create_agent_id(client, headers):
        """注册测试 Agent"""
        resp = client.post(
            "/api/v1/agents/",
            json={
                "name": "测试Agent-对话",
                "type": "assistant",
                "description": "对话测试用Agent",
            },
            headers=headers,
        )
        return resp.json()["id"]

    @staticmethod
    def _create_conv(client, headers, agent_id, title="测试对话"):
        payload = {"title": title, "agent_id": agent_id}
        resp = client.post("/api/v1/conversations/", json=payload, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_create_conversation(self, client, auth_headers):
        """创建对话"""
        agent_id = self._create_agent_id(client, auth_headers)
        data = self._create_conv(client, auth_headers, agent_id)
        assert data["title"] == "测试对话"
        assert data["agent_id"] == agent_id
        assert "id" in data
        assert data["status"] == "active"

    def test_create_conversation_missing_title(self, client, auth_headers):
        """创建缺少标题的对话应失败"""
        agent_id = self._create_agent_id(client, auth_headers)
        resp = client.post(
            "/api/v1/conversations/",
            json={"agent_id": agent_id},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_list_conversations(self, client, auth_headers):
        """对话列表"""
        agent_id = self._create_agent_id(client, auth_headers)
        self._create_conv(client, auth_headers, agent_id)
        resp = client.get("/api/v1/conversations/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_conversation(self, client, auth_headers):
        """获取对话详情"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.get(f"/api/v1/conversations/{conv['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == conv["id"]

    def test_get_conversation_not_found(self, client, auth_headers):
        """获取不存在的对话"""
        resp = client.get("/api/v1/conversations/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_conversation_title(self, client, auth_headers):
        """更新对话标题"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.put(
            f"/api/v1/conversations/{conv['id']}",
            json={"title": "更新后的标题"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "更新后的标题"

    def test_update_status_archived(self, client, auth_headers):
        """归档对话"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.patch(
            f"/api/v1/conversations/{conv['id']}/status",
            json={"status": "archived"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_delete_conversation(self, client, auth_headers):
        """删除对话"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.delete(f"/api/v1/conversations/{conv['id']}", headers=auth_headers)
        assert resp.status_code == 200
        # 验证已删除
        resp = client.get(f"/api/v1/conversations/{conv['id']}", headers=auth_headers)
        assert resp.status_code == 404

    def test_search_conversations(self, client, auth_headers):
        """搜索对话"""
        agent_id = self._create_agent_id(client, auth_headers)
        self._create_conv(client, auth_headers, agent_id, title="特殊搜索词ABC123")
        resp = client.get(
            "/api/v1/conversations/?search=ABC123",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    # ---------- 消息测试 ----------

    def test_send_message(self, client, auth_headers):
        """发送消息"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"role": "user", "content": "你好"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"
        assert resp.json()["content"] == "你好"

    def test_send_message_invalid_role(self, client, auth_headers):
        """发送消息时使用无效角色应失败"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"role": "invalid", "content": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_list_messages(self, client, auth_headers):
        """消息列表"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        # 发送两则消息
        for role in ("user", "assistant"):
            client.post(
                f"/api/v1/conversations/{conv['id']}/messages",
                json={"role": role, "content": f"{role} says hello"},
                headers=auth_headers,
            )
        resp = client.get(
            f"/api/v1/conversations/{conv['id']}/messages?page=1&page_size=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    def test_message_with_tokens(self, client, auth_headers):
        """发送带 token 计数的消息"""
        agent_id = self._create_agent_id(client, auth_headers)
        conv = self._create_conv(client, auth_headers, agent_id)
        resp = client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"role": "assistant", "content": "Hello!", "tokens": 42, "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tokens"] == 42
        assert data["model_name"] == "gpt-4o"

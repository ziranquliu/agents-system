"""认证 API 测试"""
import pytest


class TestAuth:
    """用户认证相关测试"""

    @pytest.mark.asyncio
    async def test_health(self, client):
        """健康检查"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """注册新用户"""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "NewPass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["role"] == "user"
        assert "password" not in str(data)

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client):
        """重复用户名注册应失败"""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "another@test.com",
            "password": "Test123!@#",
        })
        assert resp.status_code in (400, 409), f"Expected conflict, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """非法邮箱格式应失败"""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "invalid_email_user",
            "email": "not-an-email",
            "password": "Test123!@#",
        })
        assert resp.status_code == 422, f"Expected validation error, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """使用用户名登录"""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "Test123!@#",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """错误密码应 401"""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "wrong_password",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """不存在的用户应 401"""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user",
            "password": "somepass",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_success(self, client, auth_headers):
        """获取当前用户信息"""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client):
        """未提供 Token 应 401"""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        """无效 Token 应 401"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_xxx"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout(self, client, auth_token):
        """登出"""
        resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged out"

"""测试配置与 Fixtures"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# 必须先设置 event_loop 策略
import platform
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """创建异步测试客户端"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client):
    """注册+登录，返回 access_token"""
    # 注册
    resp = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "testuser@test.com",
        "password": "Test123!@#",
    })
    if resp.status_code == 201:
        return resp.json()["access_token"]

    # 如果已注册过则尝试登录
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "Test123!@#",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    """带认证的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}

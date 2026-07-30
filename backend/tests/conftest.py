"""测试配置与 Fixtures"""
import asyncio
import platform
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.session import engine, Base

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():
    """覆盖 pytest-asyncio 的 event_loop fixture，使用 session 级别"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """创建异步测试客户端，自动管理数据库生命周期"""
    # 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # 清理数据库
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_token(client):
    """注册 + 登录，返回 access_token"""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@test.com",
            "password": "Test123!@#",
        },
    )
    if resp.status_code in (200, 201):
        return resp.json().get("access_token")
    # 尝试登录（用户可能已存在）
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "Test123!@#"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json().get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """带认证的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}

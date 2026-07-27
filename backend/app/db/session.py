"""
数据库会话管理 — 异步 SQLAlchemy 引擎与会话工厂
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入: 获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection():
    """启动时检查数据库连接"""
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
    except Exception as e:
        print(f"⚠️ 数据库连接失败: {e}")
        raise


async def close_db_connections():
    """关闭时释放数据库连接池"""
    await engine.dispose()

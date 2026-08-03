"""
数据库会话管理 - 修复版
支持无数据库环境下的启动
"""
import sys

# Force UTF-8 encoding (use reconfigure to avoid closing the shared buffer)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# PostgreSQL 引擎（懒连接：构造不抛错，连接失败在请求/检查时暴露）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
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
    """启动时检查数据库连接

    - 生产环境: 连接失败立即抛错，阻止“假启动”
    - 开发环境: 失败仅告警，允许启动
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[INFO] Database connection OK")
    except Exception as e:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(f"数据库连接失败，拒绝启动: {e}") from e
        print(f"[WARN] 数据库连接失败（开发环境允许启动，生产将拒绝）: {e}")


async def close_db_connections():
    """关闭时释放数据库连接"""
    try:
        await engine.dispose()
    except Exception:
        pass


def is_db_available():
    """数据库引擎已就绪（连接实际可用性由 check_db_connection/pool_pre_ping 保障）"""
    return True

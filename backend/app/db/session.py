"""
数据库会话管理 - 修复版
支持无数据库环境下的启动
"""
import sys
import io

# Force UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Try to use PostgreSQL, fall back to SQLite if not available
try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"),
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    _db_available = True
except Exception as e:
    print(f"[WARN] Database connection failed, using SQLite fallback: {e}")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=True,
    )
    _db_available = False

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
    """启动时检查数据库连接（非阻塞）"""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("[INFO] Database connection OK")
    except Exception as e:
        print(f"[WARN] Database connection failed: {e}")
        # 不抛出异常，允许启动


async def close_db_connections():
    """关闭时释放数据库连接"""
    try:
        await engine.dispose()
    except Exception:
        pass


def is_db_available():
    """检查数据库是否可用"""
    return _db_available

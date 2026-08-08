"""
Alembic 迁移环境配置 - 支持异步 SQLAlchemy
"""
import asyncio
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

import sys
sys.path.insert(0, '.')  # 确保能找到 app 包

# 加载 .env 文件（从项目根目录或 backend 目录）
from dotenv import load_dotenv
for _env_dir in [Path(__file__).resolve().parent.parent.parent, Path(__file__).resolve().parent.parent]:
    _env_path = _env_dir / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# 如果 .env 中有 DATABASE_URL，覆盖 alembic.ini 的配置
import os
db_url = os.getenv("DATABASE_URL")
if db_url:
    config = context.config
    config.set_main_option("sqlalchemy.url", db_url)

# Alembic Config
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有 ORM 模型以注册到 metadata
from app.db.session import Base
from app.models import *  # noqa: F403 - 确保所有模型都被导入
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步在线迁移"""
    configuration = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线迁移入口"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
应用配置管理 — 基于 pydantic-settings 的环境变量加载
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """全局应用配置"""

    # 项目信息
    PROJECT_NAME: str = "本地智能体管理系统"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://agent:agent_dev_2024@localhost:5432/agent_system"

    # Redis
    REDIS_URL: str = "redis://:agent_dev_2024@localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # MinIO (对象存储) — 当前开发环境使用本地文件系统替代
    # 生产环境部署时取消注释并配置
    # MINIO_ENDPOINT: str = "localhost:9000"
    # MINIO_ACCESS_KEY: str = "agent_admin"
    # MINIO_SECRET_KEY: str = "agent_dev_2024"
    # MINIO_BUCKET_LOGS: str = "agent-logs"
    # MINIO_BUCKET_BACKUPS: str = "backups"
    # MINIO_BUCKET_PLUGINS: str = "plugin-storage"
    STORAGE_BACKEND: str = "local"  # local | minio | s3
    STORAGE_LOCAL_PATH: str = "../data/storage"

    # Auth
    SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60 * 24  # 24 hours

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # Model Providers
    MODEL_PROVIDERS: List[str] = ["openai", "ollama", "openrouter"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

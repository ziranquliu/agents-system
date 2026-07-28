"""
应用配置管理 - 基于 pydantic-settings 的环境变量加载
"""
import secrets
from pydantic_settings import BaseSettings
from typing import List, Optional


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

    # 存储
    STORAGE_BACKEND: str = "local"  # local | minio | s3
    STORAGE_LOCAL_PATH: str = "../data/storage"

    # ============================================================
    # 认证与安全
    # ============================================================

    # JWT 密钥（生产环境务必通过环境变量设置强密钥）
    SECRET_KEY: str = secrets.token_urlsafe(48)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60 * 24  # 24 hours
    # Token 刷新
    REFRESH_TOKEN_ENABLED: bool = False
    REFRESH_TOKEN_EXPIRATION_DAYS: int = 7

    # 密码策略
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPER: bool = True
    PASSWORD_REQUIRE_LOWER: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_HASH_ITERATIONS: int = 100000

    # 登录安全
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    TOKEN_BLACKLIST_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # 安全响应头
    SECURITY_HSTS_ENABLED: bool = True
    SECURITY_CSP_ENABLED: bool = False
    SECURITY_CSP_POLICY: Optional[str] = None

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"

    # Model Providers
    MODEL_PROVIDERS: List[str] = ["openai", "ollama", "openrouter"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

"""
加密工具模块
提供API Key等敏感数据的加密存储和检索功能
"""
import os
import logging
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class EncryptionHelper:
    """加密助手类"""
    
    _fernet = None
    _key = None
    _key_source = None  # "default" | "explicit"
    
    @classmethod
    def initialize(cls, secret_key: str = None):
        """初始化加密密钥（幂等）

        已初始化时仅允许“默认开发密钥 → 真实密钥”的升级替换，避免懒加载
        （encrypt/decrypt 无参调用）先占用默认密钥后无法换成 SECRET_KEY。
        """
        explicit = secret_key or os.getenv("ENCRYPTION_SECRET_KEY")
        if cls._fernet is not None:
            if explicit and cls._key_source == "default":
                logger.warning("检测到默认开发密钥已占位，升级为显式密钥")
            else:
                return
        
        # 无显式密钥时使用公开的默认密钥（仅限开发环境！）
        if not explicit:
            logger.warning(
                "未配置 ENCRYPTION_SECRET_KEY/SECRET_KEY，加密使用公开的默认密钥（仅限开发环境！）"
            )
            raw = "default-dev-key-change-in-production"
        else:
            raw = explicit

        key = raw.encode("utf-8")
        
        # 确保密钥为32字节（Fernet要求）
        if len(key) < 32:
            key = key.ljust(32, b"\0")
        elif len(key) > 32:
            key = key[:32]
        
        cls._key = key
        cls._key_source = "explicit" if explicit else "default"
        cls._fernet = Fernet(base64.urlsafe_b64encode(key))
    
    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """加密明文"""
        if cls._fernet is None:
            cls.initialize()
        return cls._fernet.encrypt(plaintext.encode()).decode()
    
    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """解密密文"""
        if cls._fernet is None:
            cls.initialize()
        return cls._fernet.decrypt(ciphertext.encode()).decode()
    
    @classmethod
    def mask(cls, value: str, visible_chars: int = 4) -> str:
        """掩码显示（仅显示前后几位）"""
        if not value or len(value) <= visible_chars * 2:
            return "***"
        return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]
    
    @classmethod
    def generate_key(cls) -> str:
        """生成新的加密密钥"""
        key = Fernet.generate_key()
        return base64.urlsafe_b64decode(key).decode()


# 全局实例
encryption = EncryptionHelper()

# 导出便捷函数
def encrypt_api_key(api_key: str) -> str:
    """加密API Key"""
    return encryption.encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """解密API Key"""
    return encryption.decrypt(encrypted_key)


def mask_api_key(api_key: str) -> str:
    """掩码显示API Key"""
    return encryption.mask(api_key)


# ── 幂等/后向兼容便捷函数（供业务层落库与读取时使用）──────────────
_FERNET_PREFIX = "gAAAAA"  # Fernet v1 密文的固定 base64url 前缀


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    """加密敏感字段。已是 Fernet 密文则原样返回（防重复加密）；空值返回 None。"""
    if not value:
        return None
    if value.startswith(_FERNET_PREFIX):
        return value
    return encryption.encrypt(value)


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    """解密敏感字段。非密文（明文/旧数据）原样返回；若密文无法解密（密钥变更/
    数据损坏）也原样返回而不抛异常，保证后向兼容，避免读取链路崩溃。"""
    if not value:
        return None
    if not value.startswith(_FERNET_PREFIX):
        return value
    try:
        return encryption.decrypt(value)
    except Exception:
        return value

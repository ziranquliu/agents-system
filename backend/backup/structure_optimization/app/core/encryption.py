"""
加密工具模块
提供API Key等敏感数据的加密存储和检索功能
"""
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class EncryptionHelper:
    """加密助手类"""
    
    _fernet = None
    _key = None
    
    @classmethod
    def initialize(cls, secret_key: str = None):
        """初始化加密密钥"""
        if cls._fernet is not None:
            return
        
        # 优先使用环境变量，否则生成临时密钥（仅用于开发）
        if secret_key:
            key = secret_key.encode()
        else:
            key = os.getenv("ENCRYPTION_SECRET_KEY", "default-dev-key-change-in-production")
        
        # 确保密钥为32字节
        if len(key) < 32:
            key = key.ljust(32, b'0')
        elif len(key) > 32:
            key = key[:32]
        
        cls._key = key
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

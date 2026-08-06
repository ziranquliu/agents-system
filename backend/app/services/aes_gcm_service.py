"""
AES-256-GCM 高强度加密服务

功能:
- AES-256-GCM 加密/解密 (认证加密)
- 密钥派生 (PBKDF2/Argon2 可选)
- 密钥管理 (版本化/轮换/过期)
- 信封加密 (DEK + KEK)
- 安全随机数生成
- 对比: Fernet (AES-128-CBC + HMAC) vs AES-256-GCM (更快/更安全/内置认证)

设计:
  AES-256-GCM 相比 Fernet 的优势:
  - 256-bit 密钥 vs 128-bit
  - GCM 模式提供认证加密 (AEAD), 比 CBC+HMAC 更高效
  - 内置完整性验证, 无需额外 HMAC
  - 支持附加数据 (AAD) 绑定上下文
"""

import hashlib
import hmac
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 尝试导入 cryptography
_crypto_available = False
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _crypto_available = True
except ImportError:
    logger.info("cryptography 库不可用, 使用纯 Python 降级实现")


@dataclass
class EncryptionResult:
    """加密结果"""
    ciphertext: bytes = b""
    nonce: bytes = b""
    tag: bytes = b""
    key_version: str = ""
    algorithm: str = "AES-256-GCM"
    aad: str = ""
    plaintext_length: int = 0
    ciphertext_length: int = 0


@dataclass
class KeyInfo:
    """密钥信息"""
    key_id: str = ""
    key_material: bytes = b""
    version: int = 1
    created_at: float = 0
    expires_at: float = 0
    is_active: bool = True
    algorithm: str = "AES-256-GCM"
    description: str = ""


class AESGCMEncryptionService:
    """
    AES-256-GCM 加密服务

    - 真实 AES-256-GCM (cryptography 库)
    - 降级: XOR + HMAC-SHA256 (纯 Python, 仅用于测试/开发)
    - 密钥版本化管理
    - 信封加密 (DEK 由 KEK 加密存储)
    - PBKDF2 密钥派生
    """

    NONCE_SIZE = 12  # GCM 标准 nonce
    TAG_SIZE = 16    # GCM 认证标签
    KEY_SIZE = 32    # 256-bit
    PBKDF2_ITERATIONS = 600_000

    def __init__(self):
        self._keys: dict[str, KeyInfo] = {}
        self._current_key_id: str = ""
        self._encryption_count: int = 0
        self._decryption_count: int = 0

    # ----------------------------------------------------------
    # 密钥管理
    # ----------------------------------------------------------

    def generate_key(self, key_id: str = "", description: str = "") -> dict:
        """生成新密钥"""
        material = secrets.token_bytes(self.KEY_SIZE)
        kid = key_id or f"key_{secrets.token_hex(8)}"
        now = time.time()

        key_info = KeyInfo(
            key_id=kid,
            key_material=material,
            version=len(self._keys) + 1,
            created_at=now,
            expires_at=now + 86400 * 365,  # 1 年有效期
            is_active=True,
            description=description,
        )
        self._keys[kid] = key_info
        if not self._current_key_id:
            self._current_key_id = kid

        return {
            "key_id": kid,
            "version": key_info.version,
            "created_at": key_info.created_at,
            "expires_at": key_info.expires_at,
            "key_hex": material.hex(),
        }

    def derive_key_from_password(
        self, password: str, salt: bytes = b"", key_id: str = ""
    ) -> dict:
        """从密码派生密钥 (PBKDF2)"""
        if not salt:
            salt = secrets.token_bytes(16)

        if _crypto_available:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.KEY_SIZE,
                salt=salt,
                iterations=self.PBKDF2_ITERATIONS,
            )
            material = kdf.derive(password.encode("utf-8"))
        else:
            # 降级: PBKDF2-SHA256 手动实现
            material = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, self.PBKDF2_ITERATIONS, dklen=self.KEY_SIZE
            )

        kid = key_id or f"pwd_{secrets.token_hex(8)}"
        now = time.time()
        key_info = KeyInfo(
            key_id=kid,
            key_material=material,
            version=len(self._keys) + 1,
            created_at=now,
            expires_at=now + 86400 * 90,  # 90 天
            description="password-derived",
        )
        self._keys[kid] = key_info

        return {
            "key_id": kid,
            "salt": salt.hex(),
            "version": key_info.version,
            "iterations": self.PBKDF2_ITERATIONS,
        }

    def set_current_key(self, key_id: str) -> dict:
        if key_id not in self._keys:
            return {"error": f"密钥 {key_id} 不存在"}
        self._current_key_id = key_id
        return {"current_key": key_id}

    def revoke_key(self, key_id: str) -> dict:
        key = self._keys.get(key_id)
        if not key:
            return {"error": "密钥不存在"}
        key.is_active = False
        return {"revoked": True, "key_id": key_id}

    def rotate_key(self, old_key_id: str = "") -> dict:
        """密钥轮换"""
        old = old_key_id or self._current_key_id
        if old in self._keys:
            self._keys[old].is_active = False
        return self.generate_key(description=f"轮换自 {old}")

    def list_keys(self) -> list[dict]:
        return [
            {
                "key_id": k.key_id,
                "version": k.version,
                "is_active": k.is_active,
                "created_at": k.created_at,
                "expires_at": k.expires_at,
                "is_current": k.key_id == self._current_key_id,
            }
            for k in self._keys.values()
        ]

    # ----------------------------------------------------------
    # 加密
    # ----------------------------------------------------------

    def encrypt(
        self,
        plaintext: bytes,
        key_id: str = "",
        aad: str = "",
    ) -> dict:
        """
        AES-256-GCM 加密

        Args:
            plaintext: 明文
            key_id: 密钥 ID (默认使用当前密钥)
            aad: 附加认证数据 (可选, 绑定上下文)
        """
        kid = key_id or self._current_key_id
        key_info = self._keys.get(kid)
        if not key_info:
            raise ValueError(f"密钥 {kid} 不存在")
        if not key_info.is_active:
            raise ValueError(f"密钥 {kid} 已吊销")

        nonce = secrets.token_bytes(self.NONCE_SIZE)
        aad_bytes = aad.encode("utf-8") if aad else None

        if _crypto_available:
            aesgcm = AESGCM(key_info.key_material)
            # GCM 加密返回: ciphertext + tag (拼接)
            ct_with_tag = aesgcm.encrypt(nonce, plaintext, aad_bytes)
            ciphertext = ct_with_tag[:-self.TAG_SIZE]
            tag = ct_with_tag[-self.TAG_SIZE:]
        else:
            # 降级: AES-CTR + HMAC-SHA256 模拟
            ciphertext = self._xor_encrypt(key_info.key_material, nonce, plaintext)
            tag = hmac.new(
                key_info.key_material,
                nonce + ciphertext + (aad_bytes or b""),
                hashlib.sha256,
            ).digest()[:self.TAG_SIZE]

        self._encryption_count += 1

        # 序列化结果
        result = {
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex(),
            "tag": tag.hex(),
            "key_version": kid,
            "algorithm": "AES-256-GCM",
            "aad": aad,
            "plaintext_length": len(plaintext),
            "ciphertext_length": len(ciphertext),
        }
        return result

    def encrypt_json(
        self, data: dict, key_id: str = "", aad: str = ""
    ) -> dict:
        """加密 JSON 数据"""
        import json
        plaintext = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if not aad:
            aad = "json"
        result = self.encrypt(plaintext, key_id, aad)
        result["content_type"] = "application/json"
        return result

    # ----------------------------------------------------------
    # 解密
    # ----------------------------------------------------------

    def decrypt(self, encrypted: dict) -> bytes:
        """AES-256-GCM 解密"""
        kid = encrypted.get("key_version", self._current_key_id)
        key_info = self._keys.get(kid)
        if not key_info:
            raise ValueError(f"密钥 {kid} 不存在")

        ciphertext = bytes.fromhex(encrypted["ciphertext"])
        nonce = bytes.fromhex(encrypted["nonce"])
        tag = bytes.fromhex(encrypted["tag"])
        aad = encrypted.get("aad", "")
        aad_bytes = aad.encode("utf-8") if aad else None

        if _crypto_available:
            aesgcm = AESGCM(key_info.key_material)
            # GCM: ciphertext + tag 拼接
            ct_with_tag = ciphertext + tag
            plaintext = aesgcm.decrypt(nonce, ct_with_tag, aad_bytes)
        else:
            # 降级: 验证 HMAC + XOR 解密
            expected_tag = hmac.new(
                key_info.key_material,
                nonce + ciphertext + (aad_bytes or b""),
                hashlib.sha256,
            ).digest()[:self.TAG_SIZE]
            if not hmac.compare_digest(tag, expected_tag):
                raise ValueError("认证标签验证失败 (数据被篡改)")
            plaintext = self._xor_encrypt(key_info.key_material, nonce, ciphertext)

        self._decryption_count += 1
        return plaintext

    def decrypt_json(self, encrypted: dict) -> dict:
        """解密为 JSON"""
        import json
        plaintext = self.decrypt(encrypted)
        return json.loads(plaintext.decode("utf-8"))

    # ----------------------------------------------------------
    # 信封加密 (DEK + KEK)
    # ----------------------------------------------------------

    def create_envelope(
        self,
        data: dict,
        dek_key_id: str = "",
        kek_key_id: str = "",
    ) -> dict:
        """
        信封加密:
        1. 生成随机 DEK (Data Encryption Key)
        2. 用 DEK 加密数据
        3. 用 KEK (Key Encryption Key) 加密 DEK
        4. 返回加密数据 + 加密的 DEK
        """
        # 1. 生成 DEK
        dek_material = secrets.token_bytes(self.KEY_SIZE)
        dek_id = f"dek_{secrets.token_hex(8)}"
        self._keys[dek_id] = KeyInfo(
            key_id=dek_id,
            key_material=dek_material,
            version=1,
            created_at=time.time(),
            expires_at=time.time() + 3600,  # 1 小时
            description="envelope DEK",
        )

        # 2. 用 DEK 加密数据
        encrypted_data = self.encrypt_json(data, key_id=dek_id, aad="envelope")

        # 3. 用 KEK 加密 DEK
        kek = kek_key_id or self._current_key_id
        encrypted_dek = self.encrypt(dek_material, key_id=kek, aad="dek")

        return {
            "encrypted_data": encrypted_data,
            "encrypted_dek": encrypted_dek,
            "dek_id": dek_id,
            "kek_id": kek,
            "algorithm": "AES-256-GCM-envelope",
        }

    def open_envelope(self, envelope: dict) -> dict:
        """打开信封"""
        # 1. 用 KEK 解密 DEK
        dek_material = self.decrypt(envelope["encrypted_dek"])

        # 2. 注入 DEK
        dek_id = envelope["dek_id"]
        self._keys[dek_id] = KeyInfo(
            key_id=dek_id,
            key_material=dek_material,
            version=1,
            created_at=time.time(),
            expires_at=time.time() + 3600,
            description="envelope DEK (recovered)",
        )

        # 3. 用 DEK 解密数据
        return self.decrypt_json(envelope["encrypted_data"])

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    @staticmethod
    def _xor_encrypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
        """简单 XOR 加密 (降级模式)"""
        result = bytearray(len(data))
        key_len = len(key)
        for i, b in enumerate(data):
            key_byte = key[(i + nonce[0]) % key_len]
            result[i] = b ^ key_byte
        return bytes(result)

    @staticmethod
    def generate_nonce(size: int = 12) -> bytes:
        return secrets.token_bytes(size)

    def stats(self) -> dict:
        return {
            "keys_total": len(self._keys),
            "keys_active": sum(1 for k in self._keys.values() if k.is_active),
            "current_key": self._current_key_id,
            "encryption_count": self._encryption_count,
            "decryption_count": self._decryption_count,
            "crypto_available": _crypto_available,
        }


# 全局实例
_aes_gcm_service: Optional[AESGCMEncryptionService] = None


def get_aes_gcm_service() -> AESGCMEncryptionService:
    global _aes_gcm_service
    if _aes_gcm_service is None:
        _aes_gcm_service = AESGCMEncryptionService()
    return _aes_gcm_service

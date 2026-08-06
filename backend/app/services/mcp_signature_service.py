"""
MCP 请求签名校验服务 (HMAC)

功能:
- HMAC-SHA256 签名生成
- 签名验证
- 时间窗口防重放
- 密钥管理
- 请求体序列化规范化
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SignatureKey:
    """签名密钥"""
    key_id: str = ""
    secret: str = ""
    created_at: float = 0
    expires_at: float = 0
    is_active: bool = True
    description: str = ""


@dataclass
class SignatureResult:
    """签名结果"""
    key_id: str = ""
    signature: str = ""
    timestamp: float = 0
    nonce: str = ""


@dataclass
class VerificationResult:
    """验证结果"""
    valid: bool = False
    key_id: str = ""
    error: str = ""
    timestamp: float = 0


class MCPSignatureService:
    """
    MCP 请求签名校验 (HMAC-SHA256)

    - 签名: HMAC-SHA256(secret, canonical_request)
    - 规范化: sorted_keys JSON + 按行拼接
    - 防重放: timestamp ± 300s 窗口 + nonce 缓存
    - 密钥轮换: 多 key 共存, 支持过期
    """

    MAX_TIMESTAMP_SKEW = 300  # 5 分钟窗口
    NONCE_CACHE_TTL = 600  # nonce 缓存 10 分钟
    NONCE_CACHE_MAX = 10000

    def __init__(self):
        self._keys: dict[str, SignatureKey] = {}
        self._used_nonces: dict[str, float] = {}
        self._verification_log: list[dict] = []

    # ----------------------------------------------------------
    # 密钥管理
    # ----------------------------------------------------------

    def create_key(
        self,
        key_id: str,
        secret: str,
        description: str = "",
        ttl_seconds: int = 86400 * 90,
    ) -> dict:
        """创建签名密钥"""
        now = time.time()
        key = SignatureKey(
            key_id=key_id,
            secret=secret,
            created_at=now,
            expires_at=now + ttl_seconds,
            is_active=True,
            description=description,
        )
        self._keys[key_id] = key
        return {"key_id": key_id, "created_at": now, "expires_at": key.expires_at}

    def revoke_key(self, key_id: str) -> dict:
        """吊销密钥"""
        key = self._keys.get(key_id)
        if key:
            key.is_active = False
            return {"revoked": True}
        return {"error": "密钥不存在"}

    def list_keys(self) -> list[dict]:
        """列出密钥"""
        return [
            {
                "key_id": k.key_id,
                "is_active": k.is_active,
                "created_at": k.created_at,
                "expires_at": k.expires_at,
                "description": k.description,
            }
            for k in self._keys.values()
        ]

    def rotate_key(self, old_key_id: str, new_key_id: str, new_secret: str) -> dict:
        """轮换密钥"""
        old = self._keys.get(old_key_id)
        if old:
            old.is_active = False
        return self.create_key(new_key_id, new_secret, description=f"轮换自 {old_key_id}")

    # ----------------------------------------------------------
    # 签名
    # ----------------------------------------------------------

    def sign(
        self, key_id: str, request_body: dict[str, Any], nonce: str = ""
    ) -> SignatureResult:
        """生成 HMAC 签名"""
        key = self._keys.get(key_id)
        if not key or not key.is_active:
            raise ValueError(f"密钥 {key_id} 不存在或已吊销")

        if time.time() > key.expires_at:
            raise ValueError(f"密钥 {key_id} 已过期")

        timestamp = time.time()
        canonical = self._canonicalize(request_body)
        sign_str = f"{timestamp}\n{nonce}\n{canonical}"
        signature = hmac.new(
            key.secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return SignatureResult(
            key_id=key_id,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        )

    def sign_headers(
        self, key_id: str, request_body: dict[str, Any], nonce: str = ""
    ) -> dict[str, str]:
        """生成签名 HTTP 头"""
        result = self.sign(key_id, request_body, nonce)
        return {
            "X-Signature-Key-Id": result.key_id,
            "X-Signature": result.signature,
            "X-Signature-Timestamp": str(result.timestamp),
            "X-Signature-Nonce": result.nonce,
        }

    # ----------------------------------------------------------
    # 验证
    # ----------------------------------------------------------

    def verify(
        self,
        key_id: str,
        signature: str,
        timestamp: float,
        nonce: str,
        request_body: dict[str, Any],
    ) -> VerificationResult:
        """验证签名"""
        # 时间窗口检查
        if abs(time.time() - timestamp) > self.MAX_TIMESTAMP_SKEW:
            self._log_verification(key_id, False, "timestamp_expired")
            return VerificationResult(
                valid=False, key_id=key_id, error="时间戳超出允许范围",
            )

        # Nonce 防重放
        nonce_key = f"{key_id}:{nonce}:{timestamp}"
        if nonce_key in self._used_nonces:
            self._log_verification(key_id, False, "nonce_reused")
            return VerificationResult(
                valid=False, key_id=key_id, error="Nonce 重复使用 (重放攻击)",
            )

        # 密钥检查
        key = self._keys.get(key_id)
        if not key or not key.is_active:
            self._log_verification(key_id, False, "key_invalid")
            return VerificationResult(
                valid=False, key_id=key_id, error="密钥不存在或已吊销",
            )

        if time.time() > key.expires_at:
            self._log_verification(key_id, False, "key_expired")
            return VerificationResult(
                valid=False, key_id=key_id, error="密钥已过期",
            )

        # 签名计算
        canonical = self._canonicalize(request_body)
        sign_str = f"{timestamp}\n{nonce}\n{canonical}"
        expected = hmac.new(
            key.secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # 比较 (constant-time)
        if not hmac.compare_digest(signature, expected):
            self._log_verification(key_id, False, "signature_mismatch")
            return VerificationResult(
                valid=False, key_id=key_id, error="签名不匹配",
            )

        # 记录 nonce
        self._used_nonces[nonce_key] = time.time()
        self._cleanup_nonces()

        self._log_verification(key_id, True, "ok")
        return VerificationResult(
            valid=True, key_id=key_id, timestamp=timestamp,
        )

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    def _canonicalize(self, body: dict[str, Any]) -> str:
        """规范化请求体: 递归排序键 → 紧凑 JSON"""
        return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def _cleanup_nonces(self):
        """清理过期 nonce"""
        now = time.time()
        if len(self._used_nonces) > self.NONCE_CACHE_MAX:
            expired = [
                k for k, t in self._used_nonces.items()
                if now - t > self.NONCE_CACHE_TTL
            ]
            for k in expired:
                del self._used_nonces[k]

    def _log_verification(self, key_id: str, valid: bool, reason: str):
        self._verification_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "key_id": key_id,
            "valid": valid,
            "reason": reason,
        })
        if len(self._verification_log) > 1000:
            self._verification_log = self._verification_log[-500:]

    def get_verification_log(self, limit: int = 100) -> list[dict]:
        return self._verification_log[-limit:]


# 全局实例
_mcp_signature_service: Optional[MCPSignatureService] = None


def get_mcp_signature_service() -> MCPSignatureService:
    global _mcp_signature_service
    if _mcp_signature_service is None:
        _mcp_signature_service = MCPSignatureService()
    return _mcp_signature_service

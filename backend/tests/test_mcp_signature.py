"""
测试 - MCP 签名服务 (HMAC-SHA256)
"""

import time
import pytest


class TestMCPSignature:
    """MCP 签名校验"""

    def _make_service(self):
        from app.services.mcp_signature_service import MCPSignatureService
        return MCPSignatureService()

    def test_create_key(self):
        svc = self._make_service()
        result = svc.create_key("k1", "secret123", description="test key")
        assert result["key_id"] == "k1"
        assert "expires_at" in result

    def test_list_keys(self):
        svc = self._make_service()
        svc.create_key("k1", "s1")
        svc.create_key("k2", "s2")
        keys = svc.list_keys()
        assert len(keys) == 2

    def test_revoke_key(self):
        svc = self._make_service()
        svc.create_key("k1", "s1")
        result = svc.revoke_key("k1")
        assert result["revoked"] is True
        keys = svc.list_keys()
        assert keys[0]["is_active"] is False

    def test_sign_and_verify(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        body = {"tool": "read_file", "path": "/tmp/test"}

        sign_result = svc.sign("k1", body, nonce="abc123")
        assert sign_result.key_id == "k1"
        assert len(sign_result.signature) == 64  # SHA256 hex

        verify_result = svc.verify(
            "k1", sign_result.signature, sign_result.timestamp, "abc123", body,
        )
        assert verify_result.valid is True

    def test_verify_wrong_signature(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        body = {"tool": "read_file"}

        verify_result = svc.verify(
            "k1", "wrong_signature", time.time(), "nonce1", body,
        )
        assert verify_result.valid is False
        assert "不匹配" in verify_result.error

    def test_verify_expired_timestamp(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        body = {"tool": "read_file"}

        old_time = time.time() - 600  # 10 minutes ago
        verify_result = svc.verify(
            "k1", "sig", old_time, "nonce1", body,
        )
        assert verify_result.valid is False
        assert "时间戳" in verify_result.error

    def test_verify_reused_nonce(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        body = {"tool": "read_file"}

        # 首次验证 (错误签名, 但 nonce 被记录)
        now = time.time()
        svc.verify("k1", "wrong_sig", now, "nonce1", body)
        # 第二次用相同 nonce — nonce 缓存已记录, 但签名也错, 会先命中签名不匹配
        # 需要正确签名才能触发 nonce 重放检查
        sign_result = svc.sign("k1", body, nonce="nonce2")
        verify_result = svc.verify(
            "k1", sign_result.signature, sign_result.timestamp, "nonce2", body,
        )
        assert verify_result.valid is True
        # 第二次重放
        verify_result2 = svc.verify(
            "k1", sign_result.signature, sign_result.timestamp, "nonce2", body,
        )
        assert verify_result2.valid is False
        assert "Nonce" in verify_result2.error

    def test_sign_headers(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        headers = svc.sign_headers("k1", {"data": "test"}, "nonce1")
        assert "X-Signature-Key-Id" in headers
        assert "X-Signature" in headers
        assert "X-Signature-Timestamp" in headers

    def test_rotate_key(self):
        svc = self._make_service()
        svc.create_key("k1", "old_secret")
        result = svc.rotate_key("k1", "k2", "new_secret")
        assert result["key_id"] == "k2"

        old_keys = [k for k in svc.list_keys() if k["key_id"] == "k1"]
        assert old_keys[0]["is_active"] is False

    def test_verify_log(self):
        svc = self._make_service()
        svc.create_key("k1", "my_secret")
        body = {"tool": "test"}
        now = time.time()
        svc.verify("k1", "wrong", now, "n1", body)

        log = svc.get_verification_log()
        assert len(log) >= 1
        assert log[-1]["valid"] is False

    def test_revoked_key_rejected(self):
        svc = self._make_service()
        svc.create_key("k1", "secret")
        svc.revoke_key("k1")

        with pytest.raises(ValueError, match="吊销"):
            svc.sign("k1", {"data": "test"})

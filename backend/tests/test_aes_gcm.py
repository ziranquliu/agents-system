"""
测试 - AES-256-GCM 加密服务
"""

import pytest
import json


class TestAESGCMKeyManagement:
    """密钥管理"""

    def _make_service(self):
        from app.services.aes_gcm_service import AESGCMEncryptionService
        return AESGCMEncryptionService()

    def test_generate_key(self):
        svc = self._make_service()
        result = svc.generate_key("k1", description="测试密钥")
        assert result["key_id"] == "k1"
        assert result["version"] == 1
        assert len(result["key_hex"]) == 64  # 32 bytes = 64 hex

    def test_generate_default_key_id(self):
        svc = self._make_service()
        result = svc.generate_key()
        assert result["key_id"].startswith("key_")

    def test_derive_key_from_password(self):
        svc = self._make_service()
        result = svc.derive_key_from_password("my_secure_password", key_id="pwd1")
        assert result["key_id"] == "pwd1"
        assert result["iterations"] == 600_000
        assert len(result["salt"]) == 32  # 16 bytes = 32 hex

    def test_derive_key_deterministic(self):
        svc = self._make_service()
        salt = bytes.fromhex("aabbccdd" * 4)
        r1 = svc.derive_key_from_password("pass", salt=salt, key_id="k1")
        r2 = svc.derive_key_from_password("pass", salt=salt, key_id="k2")
        # 相同密码+盐 → 相同密钥
        assert svc._keys["k1"].key_material == svc._keys["k2"].key_material

    def test_revoke_key(self):
        svc = self._make_service()
        svc.generate_key("k1")
        result = svc.revoke_key("k1")
        assert result["revoked"] is True
        assert svc._keys["k1"].is_active is False

    def test_rotate_key(self):
        svc = self._make_service()
        svc.generate_key("k1")
        result = svc.rotate_key("k1")
        assert result["key_id"] != "k1"
        assert svc._keys["k1"].is_active is False

    def test_list_keys(self):
        svc = self._make_service()
        svc.generate_key("k1")
        svc.generate_key("k2")
        keys = svc.list_keys()
        assert len(keys) == 2

    def test_set_current_key(self):
        svc = self._make_service()
        svc.generate_key("k1")
        svc.generate_key("k2")
        result = svc.set_current_key("k2")
        assert result["current_key"] == "k2"

    def test_set_nonexistent_key(self):
        svc = self._make_service()
        result = svc.set_current_key("nonexistent")
        assert "error" in result


class TestAESGCMEncryption:
    """加密/解密"""

    def _make_service_with_key(self):
        from app.services.aes_gcm_service import AESGCMEncryptionService
        svc = AESGCMEncryptionService()
        svc.generate_key("k1")
        return svc

    def test_encrypt_decrypt_bytes(self):
        svc = self._make_service_with_key()
        plaintext = b"Hello, AES-256-GCM!"
        encrypted = svc.encrypt(plaintext, key_id="k1")
        assert encrypted["algorithm"] == "AES-256-GCM"
        assert encrypted["plaintext_length"] == len(plaintext)

        decrypted = svc.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_decrypt_unicode(self):
        svc = self._make_service_with_key()
        text = "中文加密测试 🔐"
        plaintext = text.encode("utf-8")
        encrypted = svc.encrypt(plaintext, key_id="k1")
        decrypted = svc.decrypt(encrypted)
        assert decrypted.decode("utf-8") == text

    def test_encrypt_decrypt_json(self):
        svc = self._make_service_with_key()
        data = {"users": ["张三", "李四"], "count": 2, "nested": {"key": "值"}}
        encrypted = svc.encrypt_json(data, key_id="k1")
        assert encrypted["content_type"] == "application/json"

        decrypted = svc.decrypt_json(encrypted)
        assert decrypted == data

    def test_different_ciphertexts(self):
        svc = self._make_service_with_key()
        e1 = svc.encrypt(b"same data", key_id="k1")
        e2 = svc.encrypt(b"same data", key_id="k1")
        # 不同 nonce → 不同密文
        assert e1["ciphertext"] != e2["ciphertext"]

    def test_with_aad(self):
        svc = self._make_service_with_key()
        data = b"sensitive data"
        encrypted = svc.encrypt(data, key_id="k1", aad="context=binding")
        decrypted = svc.decrypt(encrypted)
        assert decrypted == data

    def test_wrong_aad_fails(self):
        svc = self._make_service_with_key()
        data = b"sensitive data"
        encrypted = svc.encrypt(data, key_id="k1", aad="correct_context")
        encrypted["aad"] = "wrong_context"
        with pytest.raises(ValueError, match="认证标签"):
            svc.decrypt(encrypted)

    def test_revoked_key_rejected(self):
        svc = self._make_service_with_key()
        svc.revoke_key("k1")
        with pytest.raises(ValueError, match="吊销"):
            svc.encrypt(b"data", key_id="k1")

    def test_nonexistent_key_rejected(self):
        svc = self._make_service_with_key()
        with pytest.raises(ValueError, match="不存在"):
            svc.encrypt(b"data", key_id="ghost")


class TestEnvelopeEncryption:
    """信封加密"""

    def _make_service(self):
        from app.services.aes_gcm_service import AESGCMEncryptionService
        svc = AESGCMEncryptionService()
        svc.generate_key("kek1")
        return svc

    def test_create_and_open_envelope(self):
        svc = self._make_service()
        data = {"secret": "top_secret_data", "users": [1, 2, 3]}
        envelope = svc.create_envelope(data, kek_key_id="kek1")
        assert envelope["algorithm"] == "AES-256-GCM-envelope"
        assert "encrypted_data" in envelope
        assert "encrypted_dek" in envelope

        decrypted = svc.open_envelope(envelope)
        assert decrypted == data

    def test_envelope_isolation(self):
        svc = self._make_service()
        e1 = svc.create_envelope({"id": 1}, kek_key_id="kek1")
        e2 = svc.create_envelope({"id": 2}, kek_key_id="kek1")
        # DEK 不同
        assert e1["dek_id"] != e2["dek_id"]


class TestAESGCMStats:
    """统计"""

    def test_stats(self):
        from app.services.aes_gcm_service import AESGCMEncryptionService
        svc = AESGCMEncryptionService()
        svc.generate_key("k1")
        svc.generate_key("k2")
        svc.revoke_key("k2")

        stats = svc.stats()
        assert stats["keys_total"] == 2
        assert stats["keys_active"] == 1
        assert stats["current_key"] == "k1"

    def test_stats_after_encryption(self):
        from app.services.aes_gcm_service import AESGCMEncryptionService
        svc = AESGCMEncryptionService()
        svc.generate_key("k1")
        svc.encrypt(b"test", key_id="k1")
        stats = svc.stats()
        assert stats["encryption_count"] == 1

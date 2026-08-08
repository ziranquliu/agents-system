"""
Tests for data_masking_service.py — 敏感字段脱敏服务
"""
import pytest
from app.services.data_masking_service import (
    DataMaskingService, MaskingType, MaskingRule, PRESET_RULES,
)


class TestMaskingTypes:
    def test_masking_type_values(self):
        assert MaskingType.IP_ADDRESS == "ip_address"
        assert MaskingType.TOKEN == "token"
        assert MaskingType.FULL_MASK == "full_mask"

    def test_preset_rules_exists(self):
        assert MaskingType.IP_ADDRESS in PRESET_RULES
        assert MaskingType.USER_ID in PRESET_RULES
        assert MaskingType.TOKEN in PRESET_RULES
        assert MaskingType.EMAIL in PRESET_RULES
        assert MaskingType.PHONE in PRESET_RULES
        assert MaskingType.CREDIT_CARD in PRESET_RULES


class TestRuleManagement:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_initial_rules(self):
        """初始有6条预置规则"""
        rules = self.svc.list_rules()
        assert len(rules) == 6

    def test_add_rule(self):
        self.svc.add_rule(MaskingRule(
            name="自定义IP",
            masking_type=MaskingType.IP_ADDRESS,
            field_name="source_ip",
        ))
        rules = self.svc.list_rules()
        assert len(rules) == 7

    def test_add_field_rule(self):
        self.svc.add_rule(MaskingRule(
            name="test",
            masking_type=MaskingType.FULL_MASK,
            field_name="secret",
        ))
        assert "secret" in self.svc._field_rules

    def test_remove_rule(self):
        self.svc.add_rule(MaskingRule(name="to_delete", masking_type=MaskingType.FULL_MASK))
        result = self.svc.remove_rule("to_delete")
        assert result is True

    def test_remove_nonexistent(self):
        result = self.svc.remove_rule("nonexistent")
        assert result is False

    def test_list_rules_structure(self):
        rules = self.svc.list_rules()
        for r in rules:
            assert "name" in r
            assert "type" in r
            assert "enabled" in r


class TestIPMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_ip_mask(self):
        masked = self.svc.mask("192.168.1.100")
        assert masked.startswith("192.168.")
        assert masked != "192.168.1.100"

    def test_ip_mask_custom_prefix(self):
        rule = MaskingRule(masking_type=MaskingType.IP_ADDRESS, preserve_prefix=1)
        masked = self.svc.mask("10.20.30.40", rule)
        assert masked.startswith("10.")
        parts = masked.split(".")
        assert parts[0] == "10"

    def test_ip_invalid_format(self):
        masked = self.svc.mask("not-an-ip")
        # 无效 IP 原样返回
        assert masked == "not-an-ip"

    def test_ip_short_ip(self):
        masked = self.svc.mask("1.2.3")
        assert masked == "1.2.3"  # 非4段原样返回


class TestIDMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_user_id_mask_explicit(self):
        """使用显式规则遮盖用户 ID"""
        rule = PRESET_RULES[MaskingType.USER_ID]
        masked = self.svc.mask("user_abc123def456", rule)
        # 前3后3保留
        assert masked[:3] == "use"
        assert masked[-3:] == "456"
        assert "***" in masked

    def test_short_id_fully_masked(self):
        """短 ID 全部遮盖"""
        rule = MaskingRule(masking_type=MaskingType.USER_ID, preserve_prefix=3, preserve_suffix=3)
        masked = self.svc.mask("ab", rule)
        assert masked == "**"  # 太短，全遮盖


class TestTokenMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_token_mask(self):
        masked = self.svc.mask("sk-abc123xyz789longtoken")
        assert masked[:4] == "sk-a"  # 前4位
        assert masked[-4:] == "oken"  # 后4位
        assert "***" in masked


class TestEmailMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_email_mask(self):
        masked = self.svc.mask("test@example.com")
        assert "@example.com" in masked
        assert masked != "test@example.com"

    def test_email_without_at(self):
        masked = self.svc.mask("noatsign")
        # 无 @ 符号按 ID 规则处理
        assert masked == "noatsign" or "***" in masked


class TestPhoneMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_phone_mask(self):
        masked = self.svc.mask("13812345678")
        # 前3后4
        assert masked[:3] == "138"
        assert masked[-4:] == "5678"
        assert "***" in masked

    def test_phone_short(self):
        masked = self.svc.mask("123")
        # 太短无法遮盖
        assert masked == "123"


class TestCreditCardMasking:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_credit_card_mask_explicit(self):
        """使用显式规则遮盖信用卡号"""
        rule = PRESET_RULES[MaskingType.CREDIT_CARD]
        masked = self.svc.mask("4111111111111234", rule)
        assert masked[-4:] == "1234"  # 保留后4位
        assert "*" in masked


class TestFullMask:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_full_mask(self):
        rule = MaskingRule(masking_type=MaskingType.FULL_MASK, mask_char="X")
        masked = self.svc.mask("secret_data", rule)
        assert masked == "XXXXXXXXXXX"

    def test_hash_mask(self):
        rule = MaskingRule(masking_type=MaskingType.HASH)
        masked = self.svc.mask("sensitive_data", rule)
        assert len(masked) == 16
        assert masked != "sensitive_data"


class TestAutoDetection:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_auto_detect_ip(self):
        masked = self.svc.mask("192.168.1.1")
        assert masked != "192.168.1.1"

    def test_auto_detect_email(self):
        masked = self.svc.mask("user@example.com")
        assert masked != "user@example.com"

    def test_unknown_type_passthrough(self):
        masked = self.svc.mask("hello world")
        assert masked == "hello world"


class TestCaching:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_cache_hit(self):
        m1 = self.svc.mask("192.168.1.1")
        m2 = self.svc.mask("192.168.1.1")
        assert m1 == m2

    def test_cache_eviction(self):
        """缓存超过 10000 条时自动清理"""
        for i in range(10005):
            self.svc.mask(f"192.168.{i % 256}.1")
        assert len(self.svc._mask_cache) <= 10001


class TestAuditConfig:
    def setup_method(self):
        self.svc = DataMaskingService()

    def test_configure_for_audit(self):
        self.svc.configure_for_audit()
        assert "operator_ip" in self.svc._field_rules
        assert "operator_id" in self.svc._field_rules
        assert "device_info" in self.svc._field_rules

    def test_disabled_rule(self):
        rule = MaskingRule(
            name="disabled",
            masking_type=MaskingType.FULL_MASK,
            enabled=False,
        )
        result = self.svc.mask("test", rule)
        assert result == "test"  # disabled → passthrough

    def test_empty_value(self):
        assert self.svc.mask("") == ""
        assert self.svc.mask(None) is None

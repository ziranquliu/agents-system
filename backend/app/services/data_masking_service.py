"""
敏感字段脱敏服务

功能:
- IP 地址脱敏（保留前两段）
- 用户 ID 脱敏（保留前3后3）
- Token/API Key 脱敏（保留前4后4）
- 手机号/邮箱脱敏
- 自定义脱敏规则
- 正则模式匹配
- 审计日志自动脱敏
- 配置持久化
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class MaskingType(str, Enum):
    IP_ADDRESS = "ip_address"
    USER_ID = "user_id"
    TOKEN = "token"
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    CUSTOM_REGEX = "custom_regex"
    HASH = "hash"           # 不可逆哈希
    FULL_MASK = "full_mask"  # 全部替换为 ***


@dataclass
class MaskingRule:
    """脱敏规则"""
    name: str = ""
    masking_type: MaskingType = MaskingType.FULL_MASK
    field_name: str = ""           # 适用字段名（空=按类型匹配）
    regex_pattern: str = ""        # 正则模式
    mask_char: str = "*"
    preserve_prefix: int = 0       # 保留前 N 位
    preserve_suffix: int = 0       # 保留后 N 位
    enabled: bool = True


# 预置规则
PRESET_RULES = {
    MaskingType.IP_ADDRESS: MaskingRule(
        name="IP脱敏",
        masking_type=MaskingType.IP_ADDRESS,
        preserve_prefix=2,
        preserve_suffix=0,
        mask_char="*",
    ),
    MaskingType.USER_ID: MaskingRule(
        name="用户ID脱敏",
        masking_type=MaskingType.USER_ID,
        preserve_prefix=3,
        preserve_suffix=3,
    ),
    MaskingType.TOKEN: MaskingRule(
        name="Token脱敏",
        masking_type=MaskingType.TOKEN,
        preserve_prefix=4,
        preserve_suffix=4,
    ),
    MaskingType.EMAIL: MaskingRule(
        name="邮箱脱敏",
        masking_type=MaskingType.EMAIL,
        preserve_prefix=2,
    ),
    MaskingType.PHONE: MaskingRule(
        name="手机号脱敏",
        masking_type=MaskingType.PHONE,
        preserve_prefix=3,
        preserve_suffix=4,
    ),
    MaskingType.CREDIT_CARD: MaskingRule(
        name="信用卡脱敏",
        masking_type=MaskingType.CREDIT_CARD,
        preserve_prefix=0,
        preserve_suffix=4,
    ),
}


class DataMaskingService:
    """
    敏感字段脱敏服务

    使用方式:
    ```python
    svc = DataMaskingService()
    svc.add_rule(MaskingRule(masking_type=MaskingType.IP_ADDRESS))
    masked = svc.mask("192.168.1.100")  # "192.168.*.*"
    ```
    """

    def __init__(self):
        self._rules: list[MaskingRule] = list(PRESET_RULES.values())
        self._field_rules: dict[str, MaskingRule] = {}  # 字段名→规则
        self._mask_cache: dict[str, str] = {}

    # ----------------------------------------------------------
    # 规则管理
    # ----------------------------------------------------------

    def add_rule(self, rule: MaskingRule):
        """添加脱敏规则"""
        self._rules.append(rule)
        if rule.field_name:
            self._field_rules[rule.field_name] = rule

    def remove_rule(self, name: str) -> bool:
        """移除脱敏规则"""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        self._field_rules = {k: v for k, v in self._field_rules.items() if v.name != name}
        return len(self._rules) < before

    def list_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "name": r.name,
                "type": r.masking_type.value,
                "field_name": r.field_name,
                "enabled": r.enabled,
                "preserve_prefix": r.preserve_prefix,
                "preserve_suffix": r.preserve_suffix,
            }
            for r in self._rules
        ]

    def configure_for_audit(self):
        """配置审计日志脱敏（一键配置）"""
        self._field_rules = {
            "operator_ip": PRESET_RULES[MaskingType.IP_ADDRESS],
            "operator_id": PRESET_RULES[MaskingType.USER_ID],
            "device_info": MaskingRule(
                name="设备信息脱敏",
                masking_type=MaskingType.CUSTOM_REGEX,
                regex_pattern=r"(Chrome|Firefox|Safari)/[\d.]+",
                field_name="device_info",
            ),
        }

    # ----------------------------------------------------------
    # 脱敏执行
    # ----------------------------------------------------------

    def mask(self, value: str, rule: Optional[MaskingRule] = None) -> str:
        """对字符串值进行脱敏"""
        if not value:
            return value

        # 缓存
        cache_key = f"{value}:{rule.name if rule else 'auto'}"
        if cache_key in self._mask_cache:
            return self._mask_cache[cache_key]

        result = self._apply_mask(value, rule)
        self._mask_cache[cache_key] = result

        # 缓存大小限制
        if len(self._mask_cache) > 10000:
            keys = list(self._mask_cache.keys())[:5000]
            for k in keys:
                del self._mask_cache[k]

        return result

    def _apply_mask(self, value: str, rule: Optional[MaskingRule] = None) -> str:
        """应用脱敏规则"""
        if rule is None:
            rule = self._detect_rule(value)

        if rule is None:
            return value

        if not rule.enabled:
            return value

        if rule.masking_type == MaskingType.IP_ADDRESS:
            return self._mask_ip(value, rule)
        elif rule.masking_type == MaskingType.USER_ID:
            return self._mask_id(value, rule)
        elif rule.masking_type == MaskingType.TOKEN:
            return self._mask_token(value, rule)
        elif rule.masking_type == MaskingType.EMAIL:
            return self._mask_email(value, rule)
        elif rule.masking_type == MaskingType.PHONE:
            return self._mask_phone(value, rule)
        elif rule.masking_type == MaskingType.CREDIT_CARD:
            return self._mask_credit_card(value, rule)
        elif rule.masking_type == MaskingType.CUSTOM_REGEX:
            return self._mask_regex(value, rule)
        elif rule.masking_type == MaskingType.HASH:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        elif rule.masking_type == MaskingType.FULL_MASK:
            return rule.mask_char * len(value)

        return value

    def _mask_ip(self, value: str, rule: MaskingRule) -> str:
        parts = value.split(".")
        if len(parts) != 4:
            return value
        masked = []
        for i, part in enumerate(parts):
            if i < rule.preserve_prefix:
                masked.append(part)
            else:
                masked.append(rule.mask_char * len(part))
        return ".".join(masked)

    def _mask_id(self, value: str, rule: MaskingRule) -> str:
        if len(value) <= rule.preserve_prefix + rule.preserve_suffix:
            return rule.mask_char * len(value)
        prefix = value[:rule.preserve_prefix]
        suffix = value[-rule.preserve_suffix:] if rule.preserve_suffix > 0 else ""
        middle = rule.mask_char * (len(value) - rule.preserve_prefix - rule.preserve_suffix)
        return prefix + middle + suffix

    def _mask_token(self, value: str, rule: MaskingRule) -> str:
        return self._mask_id(value, rule)

    def _mask_email(self, value: str, rule: MaskingRule) -> str:
        if "@" not in value:
            return self._mask_id(value, rule)
        local, domain = value.split("@", 1)
        masked_local = self._mask_id(local, MaskingRule(preserve_prefix=2, preserve_suffix=0))
        return f"{masked_local}@{domain}"

    def _mask_phone(self, value: str, rule: MaskingRule) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7:
            return rule.mask_char * len(value)
        prefix = digits[:rule.preserve_prefix]
        suffix = digits[-rule.preserve_suffix:] if rule.preserve_suffix > 0 else ""
        middle = rule.mask_char * (len(digits) - rule.preserve_prefix - rule.preserve_suffix)
        return prefix + middle + suffix

    def _mask_credit_card(self, value: str, rule: MaskingRule) -> str:
        return self._mask_id(value.replace("-", "").replace(" ", ""), rule)

    def _mask_regex(self, value: str, rule: MaskingRule) -> str:
        if not rule.regex_pattern:
            return value
        try:
            return re.sub(rule.regex_pattern, rule.mask_char * 8, value)
        except re.error:
            return value

    def _detect_rule(self, value: str) -> Optional[MaskingRule]:
        """自动检测值类型并选择规则"""
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
            return PRESET_RULES[MaskingType.IP_ADDRESS]
        if re.match(r"^[\w.-]+@[\w.-]+\.\w+$", value):
            return PRESET_RULES[MaskingType.EMAIL]
        if re.match(r"^1[3-9]\d{9}$", value):
            return PRESET_RULES[MaskingType.PHONE]
        if re.match(r"^(sk-|key-|token-)", value, re.IGNORECASE):
            return PRESET_RULES[MaskingType.TOKEN]
        return None

    # ----------------------------------------------------------
    # 批量脱敏
    # ----------------------------------------------------------

    def mask_dict(
        self,
        data: dict[str, Any],
        field_rules: Optional[dict[str, MaskingRule]] = None,
    ) -> dict[str, Any]:
        """对字典中的敏感字段进行脱敏"""
        rules = field_rules or self._field_rules
        masked = {}
        for key, value in data.items():
            if key in rules and isinstance(value, str):
                masked[key] = self.mask(value, rules[key])
            elif isinstance(value, dict):
                masked[key] = self.mask_dict(value, rules)
            elif isinstance(value, list):
                masked[key] = [
                    self.mask_dict(item, rules) if isinstance(item, dict)
                    else self.mask(item, rules.get(key)) if isinstance(item, str) and key in rules
                    else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked

    def mask_audit_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """对审计记录进行自动脱敏"""
        return self.mask_dict(record, self._field_rules)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "field_rules_count": len(self._field_rules),
            "cache_size": len(self._mask_cache),
        }

"""
密码策略校验工具
"""
import re
from app.core.config import settings


class PasswordPolicyError(ValueError):
    """密码不符合策略要求"""
    pass


def validate_password(password: str) -> None:
    """
    校验密码是否符合配置的策略

    Raises PasswordPolicyError 如果不符合要求
    """
    errors = []

    # 长度检查
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
        )

    # 大写字母
    if settings.PASSWORD_REQUIRE_UPPER and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    # 小写字母
    if settings.PASSWORD_REQUIRE_LOWER and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    # 数字
    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")

    # 特殊字符
    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=~`\[\]\\;\'/]', password):
        errors.append("Password must contain at least one special character")

    if errors:
        raise PasswordPolicyError("; ".join(errors))

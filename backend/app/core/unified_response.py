"""
统一响应格式 + 错误码体系 + RBAC 权限中间件

功能:
1. 统一响应: {"code": 0, "data": {...}, "message": "success", "request_id": "..."}
2. 错误码: AB-CDE-FG 格式 (模块-子模块-序号)
3. RBAC: 4 角色 (super_admin / admin / operator / viewer) + 50+ 权限
4. 权限装饰器 + 中间件
"""

import logging
import time
import uuid
from enum import Enum
from functools import wraps
from typing import Any, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ============================================================
# 1. 统一响应格式
# ============================================================

class ResponseCode:
    """标准响应码"""
    SUCCESS = 0
    PARAM_ERROR = 1001
    AUTH_FAILED = 2001
    AUTH_TOKEN_EXPIRED = 2002
    AUTH_TOKEN_INVALID = 2003
    PERMISSION_DENIED = 2004
    RESOURCE_NOT_FOUND = 3001
    RESOURCE_CONFLICT = 3002
    RATE_LIMITED = 3003
    INTERNAL_ERROR = 5001
    SERVICE_UNAVAILABLE = 5002
    DEPENDENCY_FAILED = 5003


# ============================================================
# 2. 错误码体系 (AB-CDE-FG)
# ============================================================

class ErrorCode(Enum):
    """
    错误码体系

    格式: AB-CDE-FG
      AB  = 模块码 (01-99)
      CDE = 子模块码 (001-999)
      FG  = 序号 (01-99)
    """

    # --- 通用 (00-xxx) ---
    SUCCESS = "00-000-01"
    UNKNOWN_ERROR = "00-000-99"
    PARAM_MISSING = "00-001-01"
    PARAM_INVALID = "00-001-02"
    PARAM_TYPE_ERROR = "00-001-03"
    REQUEST_TOO_FREQUENT = "00-002-01"
    REQUEST_TIMEOUT = "00-002-02"

    # --- 认证/授权 (01-xxx) ---
    AUTH_FAILED = "01-001-01"
    TOKEN_EXPIRED = "01-001-02"
    TOKEN_INVALID = "01-001-03"
    TOKEN_MISSING = "01-001-04"
    PERMISSION_DENIED = "01-002-01"
    ROLE_NOT_FOUND = "01-002-02"
    ACCOUNT_DISABLED = "01-003-01"
    ACCOUNT_LOCKED = "01-003-02"
    LOGIN_FAILED = "01-004-01"
    LOGOUT_FAILED = "01-004-02"

    # --- Agent 管理 (02-xxx) ---
    AGENT_NOT_FOUND = "02-001-01"
    AGENT_ALREADY_EXISTS = "02-001-02"
    AGENT_CONFIG_INVALID = "02-001-03"
    AGENT_START_FAILED = "02-002-01"
    AGENT_STOP_FAILED = "02-002-02"
    AGENT_UNHEALTHY = "02-003-01"
    AGENT_VERSION_CONFLICT = "02-004-01"

    # --- 模型管理 (03-xxx) ---
    MODEL_NOT_FOUND = "03-001-01"
    MODEL_CONFIG_INVALID = "03-001-02"
    MODEL_API_KEY_MISSING = "03-001-03"
    MODEL_PROVIDER_ERROR = "03-002-01"
    MODEL_QUOTA_EXCEEDED = "03-002-02"
    MODEL_SWITCH_FAILED = "03-003-01"

    # --- 技能管理 (04-xxx) ---
    SKILL_NOT_FOUND = "04-001-01"
    SKILL_INSTALL_FAILED = "04-002-01"
    SKILL_UNINSTALL_FAILED = "04-002-02"
    SKILL_VERSION_CONFLICT = "04-003-01"
    SKILL_DEPENDENCY_MISSING = "04-003-02"
    SKILL_CONFLICT = "04-003-03"

    # --- MCP 管理 (05-xxx) ---
    MCP_NOT_FOUND = "05-001-01"
    MCP_CONNECTION_FAILED = "05-002-01"
    MCP_TIMEOUT = "05-002-02"
    MCP_AUTH_FAILED = "05-002-03"
    MCP_RATE_LIMITED = "05-003-01"
    MCP_SIGNATURE_INVALID = "05-003-02"

    # --- 会话管理 (06-xxx) ---
    SESSION_NOT_FOUND = "06-001-01"
    SESSION_EXPIRED = "06-001-02"
    SESSION_FULL = "06-001-03"
    SESSION_MIGRATION_FAILED = "06-002-01"

    # --- 知识库 (07-xxx) ---
    KNOWLEDGE_NOT_FOUND = "07-001-01"
    KNOWLEDGE_INDEX_FAILED = "07-002-01"
    KNOWLEDGE_SEARCH_FAILED = "07-002-02"

    # --- Token/预算 (08-xxx) ---
    TOKEN_QUOTA_EXCEEDED = "08-001-01"
    BUDGET_EXCEEDED = "08-001-02"
    COST_LIMIT_REACHED = "08-001-03"

    # --- 工作流 (09-xxx) ---
    WORKFLOW_NOT_FOUND = "09-001-01"
    WORKFLOW_CYCLE_DETECTED = "09-002-01"
    WORKFLOW_NODE_FAILED = "09-003-01"
    WORKFLOW_TIMEOUT = "09-003-02"

    # --- 备份恢复 (10-xxx) ---
    BACKUP_FAILED = "10-001-01"
    BACKUP_NOT_FOUND = "10-001-02"
    RESTORE_FAILED = "10-002-01"
    RESTORE_INCOMPATIBLE = "10-002-02"
    CHECKSUM_MISMATCH = "10-003-01"

    # --- 系统/监控 (11-xxx) ---
    SYSTEM_OVERLOADED = "11-001-01"
    DATABASE_UNAVAILABLE = "11-002-01"
    REDIS_UNAVAILABLE = "11-002-02"
    QDRANT_UNAVAILABLE = "11-002-03"
    S3_UNAVAILABLE = "11-002-04"

    # --- 协作 (12-xxx) ---
    COLLAB_MODE_INVALID = "12-001-01"
    AGENT_BUSY = "12-002-01"
    MESSAGE_SEND_FAILED = "12-003-01"

    # --- 数据脱敏 (13-xxx) ---
    MASKING_RULE_INVALID = "13-001-01"

    @property
    def http_status(self) -> int:
        """映射到 HTTP 状态码"""
        module = int(self.value.split("-")[0])
        if self == ErrorCode.SUCCESS:
            return 200
        if module <= 1:
            return 401
        if module == 1 and "PERMISSION" in self.name:
            return 403
        if module <= 13 and any(
            kw in self.name
            for kw in ["NOT_FOUND", "MISSING", "EXPIRED", "CONFLICT"]
        ):
            return 404
        if "RATE_LIMIT" in self.name or "QUOTA_EXCEEDED" in self.name:
            return 429
        if "PARAM_" in self.name:
            return 400
        return 500

    @property
    def message(self) -> str:
        """人类可读错误消息"""
        messages = {
            ErrorCode.SUCCESS: "操作成功",
            ErrorCode.UNKNOWN_ERROR: "未知错误",
            ErrorCode.PARAM_MISSING: "缺少必要参数",
            ErrorCode.PARAM_INVALID: "参数无效",
            ErrorCode.PARAM_TYPE_ERROR: "参数类型错误",
            ErrorCode.REQUEST_TOO_FREQUENT: "请求过于频繁",
            ErrorCode.REQUEST_TIMEOUT: "请求超时",
            ErrorCode.AUTH_FAILED: "认证失败",
            ErrorCode.TOKEN_EXPIRED: "Token 已过期",
            ErrorCode.TOKEN_INVALID: "Token 无效",
            ErrorCode.TOKEN_MISSING: "缺少 Token",
            ErrorCode.PERMISSION_DENIED: "权限不足",
            ErrorCode.ROLE_NOT_FOUND: "角色不存在",
            ErrorCode.ACCOUNT_DISABLED: "账户已禁用",
            ErrorCode.ACCOUNT_LOCKED: "账户已锁定",
            ErrorCode.LOGIN_FAILED: "登录失败",
            ErrorCode.AGENT_NOT_FOUND: "Agent 不存在",
            ErrorCode.AGENT_ALREADY_EXISTS: "Agent 已存在",
            ErrorCode.MODEL_NOT_FOUND: "模型不存在",
            ErrorCode.MODEL_API_KEY_MISSING: "模型 API Key 未配置",
            ErrorCode.MODEL_QUOTA_EXCEEDED: "模型配额已用完",
            ErrorCode.SKILL_NOT_FOUND: "技能不存在",
            ErrorCode.SKILL_INSTALL_FAILED: "技能安装失败",
            ErrorCode.SKILL_DEPENDENCY_MISSING: "技能依赖缺失",
            ErrorCode.SKILL_CONFLICT: "技能冲突",
            ErrorCode.MCP_NOT_FOUND: "MCP 服务不存在",
            ErrorCode.MCP_CONNECTION_FAILED: "MCP 连接失败",
            ErrorCode.MCP_SIGNATURE_INVALID: "MCP 签名验证失败",
            ErrorCode.SESSION_NOT_FOUND: "会话不存在",
            ErrorCode.SESSION_EXPIRED: "会话已过期",
            ErrorCode.KNOWLEDGE_NOT_FOUND: "知识条目不存在",
            ErrorCode.TOKEN_QUOTA_EXCEEDED: "Token 配额已用完",
            ErrorCode.BUDGET_EXCEEDED: "预算已超支",
            ErrorCode.WORKFLOW_NOT_FOUND: "工作流不存在",
            ErrorCode.WORKFLOW_CYCLE_DETECTED: "工作流存在循环依赖",
            ErrorCode.BACKUP_FAILED: "备份失败",
            ErrorCode.RESTORE_FAILED: "恢复失败",
            ErrorCode.CHECKSUM_MISMATCH: "校验和不匹配, 数据可能被篡改",
            ErrorCode.DATABASE_UNAVAILABLE: "数据库不可用",
            ErrorCode.REDIS_UNAVAILABLE: "Redis 不可用",
        }
        return messages.get(self, "未知错误")


class UnifiedResponse:
    """统一响应构建器"""

    @staticmethod
    def success(data: Any = None, message: str = "success", request_id: str = "") -> dict:
        return {
            "code": 0,
            "data": data,
            "message": message,
            "request_id": request_id or uuid.uuid4().hex[:12],
            "timestamp": int(time.time() * 1000),
        }

    @staticmethod
    def error(
        error_code: ErrorCode,
        message: str = "",
        data: Any = None,
        request_id: str = "",
    ) -> dict:
        return {
            "code": error_code.http_status,
            "error_code": error_code.value,
            "data": data,
            "message": message or error_code.message,
            "request_id": request_id or uuid.uuid4().hex[:12],
            "timestamp": int(time.time() * 1000),
        }

    @staticmethod
    def paginated(
        items: list,
        total: int,
        page: int = 1,
        page_size: int = 20,
        request_id: str = "",
    ) -> dict:
        return {
            "code": 0,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            },
            "message": "success",
            "request_id": request_id or uuid.uuid4().hex[:12],
            "timestamp": int(time.time() * 1000),
        }


# ============================================================
# 3. RBAC 权限模型
# ============================================================

class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# 50+ 权限定义
class Permission(str, Enum):
    # Agent 管理
    AGENT_VIEW = "agent:view"
    AGENT_CREATE = "agent:create"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_START = "agent:start"
    AGENT_STOP = "agent:stop"
    AGENT_RESTART = "agent:restart"
    AGENT_CONFIG = "agent:config"

    # 模型管理
    MODEL_VIEW = "model:view"
    MODEL_CREATE = "model:create"
    MODEL_UPDATE = "model:update"
    MODEL_DELETE = "model:delete"
    MODEL_SWITCH = "model:switch"
    MODEL_KEY_MANAGE = "model:key_manage"

    # 技能管理
    SKILL_VIEW = "skill:view"
    SKILL_INSTALL = "skill:install"
    SKILL_UNINSTALL = "skill:uninstall"
    SKILL_UPDATE = "skill:update"
    SKILL_CONFIG = "skill:config"

    # MCP 管理
    MCP_VIEW = "mcp:view"
    MCP_CREATE = "mcp:create"
    MCP_UPDATE = "mcp:update"
    MCP_DELETE = "mcp:delete"
    MCP_CONNECT = "mcp:connect"
    MCP_SIGNATURE = "mcp:signature"

    # 会话管理
    SESSION_VIEW = "session:view"
    SESSION_CREATE = "session:create"
    SESSION_DELETE = "session:delete"
    SESSION_EXPORT = "session:export"
    SESSION_MIGRATE = "session:migrate"

    # 知识库
    KNOWLEDGE_VIEW = "knowledge:view"
    KNOWLEDGE_CREATE = "knowledge:create"
    KNOWLEDGE_UPDATE = "knowledge:update"
    KNOWLEDGE_DELETE = "knowledge:delete"
    KNOWLEDGE_SEARCH = "knowledge:search"

    # Token/预算
    TOKEN_VIEW = "token:view"
    TOKEN_MANAGE = "token:manage"
    BUDGET_VIEW = "budget:view"
    BUDGET_MANAGE = "budget:manage"

    # 工作流
    WORKFLOW_VIEW = "workflow:view"
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"

    # 备份恢复
    BACKUP_VIEW = "backup:view"
    BACKUP_CREATE = "backup:create"
    BACKUP_RESTORE = "backup:restore"
    BACKUP_DELETE = "backup:delete"

    # 系统管理
    SYSTEM_VIEW = "system:view"
    SYSTEM_CONFIG = "system:config"
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"
    LOG_VIEW = "log:view"

    # 协作
    COLLAB_VIEW = "collab:view"
    COLLAB_MANAGE = "collab:manage"

    # 监控
    MONITOR_VIEW = "monitor:view"
    MONITOR_ALERT = "monitor:alert"
    DASHBOARD_MANAGE = "dashboard:manage"


# 角色 → 权限映射
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # 全部权限
    Role.ADMIN: {
        Permission.AGENT_VIEW, Permission.AGENT_CREATE, Permission.AGENT_UPDATE,
        Permission.AGENT_DELETE, Permission.AGENT_START, Permission.AGENT_STOP,
        Permission.AGENT_RESTART, Permission.AGENT_CONFIG,
        Permission.MODEL_VIEW, Permission.MODEL_CREATE, Permission.MODEL_UPDATE,
        Permission.MODEL_DELETE, Permission.MODEL_SWITCH,
        Permission.SKILL_VIEW, Permission.SKILL_INSTALL, Permission.SKILL_UNINSTALL,
        Permission.SKILL_UPDATE, Permission.SKILL_CONFIG,
        Permission.MCP_VIEW, Permission.MCP_CREATE, Permission.MCP_UPDATE,
        Permission.MCP_DELETE, Permission.MCP_CONNECT,
        Permission.SESSION_VIEW, Permission.SESSION_CREATE, Permission.SESSION_DELETE,
        Permission.SESSION_EXPORT,
        Permission.KNOWLEDGE_VIEW, Permission.KNOWLEDGE_CREATE, Permission.KNOWLEDGE_UPDATE,
        Permission.KNOWLEDGE_DELETE, Permission.KNOWLEDGE_SEARCH,
        Permission.TOKEN_VIEW, Permission.TOKEN_MANAGE,
        Permission.BUDGET_VIEW, Permission.BUDGET_MANAGE,
        Permission.WORKFLOW_VIEW, Permission.WORKFLOW_CREATE, Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_DELETE, Permission.WORKFLOW_EXECUTE,
        Permission.BACKUP_VIEW, Permission.BACKUP_CREATE, Permission.BACKUP_RESTORE,
        Permission.SYSTEM_VIEW, Permission.USER_MANAGE, Permission.ROLE_MANAGE,
        Permission.AUDIT_VIEW, Permission.LOG_VIEW,
        Permission.COLLAB_VIEW, Permission.COLLAB_MANAGE,
        Permission.MONITOR_VIEW, Permission.MONITOR_ALERT, Permission.DASHBOARD_MANAGE,
    },
    Role.OPERATOR: {
        Permission.AGENT_VIEW, Permission.AGENT_START, Permission.AGENT_STOP,
        Permission.MODEL_VIEW, Permission.MODEL_SWITCH,
        Permission.SKILL_VIEW, Permission.SKILL_INSTALL,
        Permission.MCP_VIEW, Permission.MCP_CONNECT,
        Permission.SESSION_VIEW, Permission.SESSION_CREATE, Permission.SESSION_EXPORT,
        Permission.KNOWLEDGE_VIEW, Permission.KNOWLEDGE_SEARCH,
        Permission.TOKEN_VIEW, Permission.BUDGET_VIEW,
        Permission.WORKFLOW_VIEW, Permission.WORKFLOW_EXECUTE,
        Permission.BACKUP_VIEW, Permission.BACKUP_CREATE,
        Permission.SYSTEM_VIEW, Permission.AUDIT_VIEW, Permission.LOG_VIEW,
        Permission.COLLAB_VIEW,
        Permission.MONITOR_VIEW,
    },
    Role.VIEWER: {
        Permission.AGENT_VIEW,
        Permission.MODEL_VIEW,
        Permission.SKILL_VIEW,
        Permission.MCP_VIEW,
        Permission.SESSION_VIEW,
        Permission.KNOWLEDGE_VIEW,
        Permission.TOKEN_VIEW, Permission.BUDGET_VIEW,
        Permission.WORKFLOW_VIEW,
        Permission.BACKUP_VIEW,
        Permission.SYSTEM_VIEW, Permission.AUDIT_VIEW,
        Permission.COLLAB_VIEW,
        Permission.MONITOR_VIEW,
    },
}


# ============================================================
# 4. RBAC 中间件
# ============================================================

class RBACMiddleware:
    """
    RBAC 权限中间件

    - 从 JWT Token 中提取 user_id 和 role
    - 验证请求路径 + HTTP 方法 → 所需权限
    - 检查角色是否拥有该权限
    """

    # 路径 → 权限映射
    PATH_PERMISSION_MAP: dict[tuple[str, str], Permission] = {
        # Agent
        ("GET", "/api/v1/agents"): Permission.AGENT_VIEW,
        ("GET", "/api/v1/agents/{id}"): Permission.AGENT_VIEW,
        ("POST", "/api/v1/agents"): Permission.AGENT_CREATE,
        ("PUT", "/api/v1/agents/{id}"): Permission.AGENT_UPDATE,
        ("DELETE", "/api/v1/agents/{id}"): Permission.AGENT_DELETE,
        ("POST", "/api/v1/agents/{id}/start"): Permission.AGENT_START,
        ("POST", "/api/v1/agents/{id}/stop"): Permission.AGENT_STOP,
        # 模型
        ("GET", "/api/v1/models"): Permission.MODEL_VIEW,
        ("POST", "/api/v1/models"): Permission.MODEL_CREATE,
        ("PUT", "/api/v1/models/{id}"): Permission.MODEL_UPDATE,
        ("DELETE", "/api/v1/models/{id}"): Permission.MODEL_DELETE,
        ("POST", "/api/v1/hotswap/switch"): Permission.MODEL_SWITCH,
        # 技能
        ("GET", "/api/v1/skills"): Permission.SKILL_VIEW,
        ("POST", "/api/v1/skills/install"): Permission.SKILL_INSTALL,
        ("DELETE", "/api/v1/skills/{id}"): Permission.SKILL_UNINSTALL,
        # MCP
        ("GET", "/api/v1/mcp"): Permission.MCP_VIEW,
        ("POST", "/api/v1/mcp"): Permission.MCP_CREATE,
        ("POST", "/api/v1/mcp/connect"): Permission.MCP_CONNECT,
        # 会话
        ("GET", "/api/v1/sessions"): Permission.SESSION_VIEW,
        ("POST", "/api/v1/sessions"): Permission.SESSION_CREATE,
        ("DELETE", "/api/v1/sessions/{id}"): Permission.SESSION_DELETE,
        # 知识库
        ("GET", "/api/v1/knowledge"): Permission.KNOWLEDGE_VIEW,
        ("POST", "/api/v1/knowledge"): Permission.KNOWLEDGE_CREATE,
        ("POST", "/api/v1/knowledge/search"): Permission.KNOWLEDGE_SEARCH,
        # Token/预算
        ("GET", "/api/v1/quotas"): Permission.TOKEN_VIEW,
        ("POST", "/api/v1/quotas"): Permission.TOKEN_MANAGE,
        # 工作流
        ("GET", "/api/v1/workflows"): Permission.WORKFLOW_VIEW,
        ("POST", "/api/v1/workflows"): Permission.WORKFLOW_CREATE,
        ("POST", "/api/v1/workflows/{id}/execute"): Permission.WORKFLOW_EXECUTE,
        # 备份
        ("GET", "/api/v1/backups"): Permission.BACKUP_VIEW,
        ("POST", "/api/v1/backups"): Permission.BACKUP_CREATE,
        ("POST", "/api/v1/backups/{id}/restore"): Permission.BACKUP_RESTORE,
        # 系统
        ("GET", "/api/v1/system"): Permission.SYSTEM_VIEW,
        ("PUT", "/api/v1/system/config"): Permission.SYSTEM_CONFIG,
        ("GET", "/api/v1/audit"): Permission.AUDIT_VIEW,
    }

    # 无需认证的路径
    PUBLIC_PATHS = {
        "/docs", "/redoc", "/openapi.json",
        "/api/v1/auth/login", "/api/v1/auth/register",
        "/health", "/health/ready", "/metrics",
    }

    def __init__(self):
        self._user_roles: dict[str, str] = {}  # user_id -> role

    def set_user_role(self, user_id: str, role: str):
        """设置用户角色"""
        self._user_roles[user_id] = role

    def get_user_role(self, user_id: str) -> str:
        return self._user_roles.get(user_id, Role.VIEWER.value)

    def get_user_permissions(self, user_id: str) -> set[Permission]:
        """获取用户权限集"""
        role_str = self.get_user_role(user_id)
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.VIEWER
        return ROLE_PERMISSIONS.get(role, set())

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """检查用户是否有某权限"""
        permissions = self.get_user_permissions(user_id)
        return permission in permissions

    def get_required_permission(self, method: str, path: str) -> Optional[Permission]:
        """获取路径所需权限"""
        # 简化路径匹配 (去掉路径参数值)
        normalized = path
        for segment in path.split("/"):
            if segment and not segment.startswith("{") and len(segment) > 20:
                normalized = normalized.replace(segment, "{id}")

        # 尝试直接匹配
        direct_key = (method.upper(), path)
        if direct_key in self.PATH_PERMISSION_MAP:
            return self.PATH_PERMISSION_MAP[direct_key]

        # 模糊匹配
        for (m, p), perm in self.PATH_PERMISSION_MAP.items():
            if m != method.upper():
                continue
            pattern_parts = p.split("/")
            path_parts = path.split("/")
            if len(pattern_parts) != len(path_parts):
                continue
            match = True
            for pp, rp in zip(pattern_parts, path_parts):
                if pp.startswith("{"):
                    continue
                if pp != rp:
                    match = False
                    break
            if match:
                return perm

        return None

    def is_public_path(self, path: str) -> bool:
        return path in self.PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")


# 全局实例
_rbac_middleware: Optional[RBACMiddleware] = None


def get_rbac_middleware() -> RBACMiddleware:
    global _rbac_middleware
    if _rbac_middleware is None:
        _rbac_middleware = RBACMiddleware()
    return _rbac_middleware


# ============================================================
# 5. 权限检查装饰器
# ============================================================

def require_permission(permission: Permission):
    """权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    rbac = get_rbac_middleware()
                    if not rbac.check_permission(user_id, permission):
                        return JSONResponse(
                            status_code=403,
                            content=UnifiedResponse.error(
                                ErrorCode.PERMISSION_DENIED,
                                f"需要权限: {permission.value}",
                            ),
                        )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """角色装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    rbac = get_rbac_middleware()
                    user_role = rbac.get_user_role(user_id)
                    try:
                        user_role_enum = Role(user_role)
                    except ValueError:
                        user_role_enum = Role.VIEWER

                    # super_admin > admin > operator > viewer
                    role_hierarchy = {
                        Role.SUPER_ADMIN: 4,
                        Role.ADMIN: 3,
                        Role.OPERATOR: 2,
                        Role.VIEWER: 1,
                    }
                    if role_hierarchy.get(user_role_enum, 0) < role_hierarchy.get(role, 0):
                        return JSONResponse(
                            status_code=403,
                            content=UnifiedResponse.error(
                                ErrorCode.PERMISSION_DENIED,
                                f"需要角色: {role.value}",
                            ),
                        )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

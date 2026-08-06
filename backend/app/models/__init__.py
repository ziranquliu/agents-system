"""
ORM 模型统一导出

显式 re-export：通过 __all__ 声明公共 API，使 ruff/IDE 识别为有意导出。
Alembic autogenerate 与 pytest fixtures 依赖这些导入触发 Base.metadata 注册。
"""
from app.db.session import Base  # noqa: F401

from app.models.user import User, Role, OperationLog  # noqa: F401
from app.models.agent import Agent, ModelConfigTemplate  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.workspace import Workspace, WorkspaceMember  # noqa: F401
from app.models.skill import Skill, SkillBinding, MCPServer  # noqa: F401
from app.models.scanner import ComponentScan, ComponentScanItem, ScannerAlert  # noqa: F401
from app.models.collaboration import Collaboration, CollaborationTask  # noqa: F401
from app.models.knowledge import KnowledgeBase, KnowledgeDocument, KnowledgeChunk  # noqa: F401
from app.models.semantic_cache import SemanticCacheEntry  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.memory import AgentMemory, MemoryAnalytics  # noqa: F401
from app.models.model_template import ModelTemplateVersion, ModelTemplateBinding  # noqa: F401
from app.models.batch_install import BatchInstallQueue, BatchInstallItem  # noqa: F401
from app.models.skill_reuse import SkillReuseRelation  # noqa: F401
from app.models.mcp_batch import MCPAgentBinding, MCPBatchInstallQueue, MCPBatchInstallItem  # noqa: F401
from app.models.dialogue_enhancement import HumanIntervention, DialogueRating, RatingAnalytics  # noqa: F401
from app.models.monitoring import AgentMetric, AlertConfig, AlertRecord, DashboardPanel  # noqa: F401
from app.models.ops import (  # noqa: F401
    AgentDeployment, ScalingPolicy, ScalingEvent, LogEntry, LogCollectionConfig,
    MaintenanceTask, MaintenanceExecution, SelfHealRecord, HealRule, OpsReport
)
from app.models.backup_enhanced import (  # noqa: F401
    BackupRecord, BackupPolicy, BackupEventLog, RestoreOperation,
    RestoreDrill, EncryptionKey, BackupType, BackupStatus, BackupScope,
    RestoreType, RestoreStatus, DrillStatus, EncryptionAlgo,
)
from app.models.health import (  # noqa: F401
    HealthCheckRun, HealthSnapshot, HealthScoreWeight, AgentHealthConfig,
    HealthTrendPoint, HealthEvent, HealthLevel, CheckStatus,
    AgentHealthStatus,
)
from app.models.audit import (  # noqa: F401
    AuditLog, AuditArchive, AuditRule, AuditAlert, AuditConfig,
    AuditCategory, AuditResult, AnomalyType, AlertSeverity,
)
from app.models.token import (  # noqa: F401
    TokenUsage, TokenBudget, TokenAlert, ModelCascadeRule, TokenOptimizationStat,
)
from app.models.update_enhanced import UpdateSnapshot, UpdateLog  # noqa: F401
from app.models.notification import NotificationConfig, NotifyMethod  # noqa: F401
from app.models.event_log import EventLog, DeadLetterQueue  # noqa: F401

__all__ = [
    "Base",
    "User", "Role", "OperationLog",
    "Agent", "ModelConfigTemplate",
    "Conversation", "Message",
    "Workspace", "WorkspaceMember",
    "Skill", "SkillBinding", "MCPServer",
    "ComponentScan", "ComponentScanItem", "ScannerAlert",
    "Collaboration", "CollaborationTask",
    "KnowledgeBase", "KnowledgeDocument", "KnowledgeChunk",
    "SemanticCacheEntry",
    "Task",
    "AgentMemory", "MemoryAnalytics",
    "ModelTemplateVersion", "ModelTemplateBinding",
    "BatchInstallQueue", "BatchInstallItem",
    "SkillReuseRelation",
    "MCPAgentBinding", "MCPBatchInstallQueue", "MCPBatchInstallItem",
    "HumanIntervention", "DialogueRating", "RatingAnalytics",
    "AgentMetric", "AlertConfig", "AlertRecord", "DashboardPanel",
    "AgentDeployment", "ScalingPolicy", "ScalingEvent", "LogEntry", "LogCollectionConfig",
    "MaintenanceTask", "MaintenanceExecution", "SelfHealRecord", "HealRule", "OpsReport",
    "BackupRecord", "BackupPolicy", "BackupEventLog", "RestoreOperation",
    "RestoreDrill", "EncryptionKey", "BackupType", "BackupStatus", "BackupScope",
    "RestoreType", "RestoreStatus", "DrillStatus", "EncryptionAlgo",
    "HealthCheckRun", "HealthSnapshot", "HealthScoreWeight", "AgentHealthConfig",
    "HealthTrendPoint", "HealthEvent", "HealthLevel", "CheckStatus", "AgentHealthStatus",
    "AuditLog", "AuditArchive", "AuditRule", "AuditAlert", "AuditConfig",
    "AuditCategory", "AuditResult", "AnomalyType", "AlertSeverity",
    "TokenUsage", "TokenBudget", "TokenAlert", "ModelCascadeRule", "TokenOptimizationStat",
    "UpdateSnapshot", "UpdateLog",
    "NotificationConfig", "NotifyMethod",
    "EventLog", "DeadLetterQueue",
]

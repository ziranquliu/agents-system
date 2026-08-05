"""API v1 路由聚合 - 最终版本"""
from fastapi import APIRouter
from app.api.v1 import (
    auth, agents, models, chat, conversations, skills, workspaces, 
    mcp_servers, discovery, operation_logs, users, mcp_market, 
    skill_market, agent_market, model_market, scanner, updates, 
    collaborations, skill_optimization, mcp_optimization, 
    conversation_enhancement, knowledge, tasks, system_monitor, 
    backup, backup_enhanced, memory, model_templates, batch_install, 
    skill_reuse, mcp_batch, dialogue_enhancement, monitoring, ops, 
    health, audit, scheduler, tokens, workflows
)

api_router = APIRouter()

# Authentication
api_router.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])

# Core entities
api_router.include_router(agents.router, prefix="/api/v1/agents", tags=["Agent管理"])
api_router.include_router(models.router, prefix="/api/v1/models", tags=["模型配置"])
api_router.include_router(skills.router, prefix="/api/v1/skills", tags=["Skill管理"])
api_router.include_router(mcp_servers.router, prefix="/api/v1/mcp-servers", tags=["MCP Server管理"])
api_router.include_router(conversations.router, prefix="/api/v1/conversations", tags=["对话历史"])
api_router.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["工作区管理"])
api_router.include_router(users.router, prefix="/api/v1", tags=["用户管理"])

# Discovery & Operations
api_router.include_router(discovery.router, prefix="/api/v1/discover", tags=["Agent发现"])
api_router.include_router(operation_logs.router, prefix="/api/v1", tags=["操作日志"])
api_router.include_router(scanner.router, prefix="/api/v1", tags=["组件扫描器"])
api_router.include_router(updates.router, prefix="/api/v1", tags=["更新检测"])

# Markets
api_router.include_router(mcp_market.router, prefix="/api/v1", tags=["MCP 在线市场"])
api_router.include_router(skill_market.router, prefix="/api/v1", tags=["Skill 在线市场"])
api_router.include_router(agent_market.router, prefix="/api/v1", tags=["Agent 在线市场"])
api_router.include_router(model_market.router, prefix="/api/v1", tags=["模型在线市场"])

# Enhancement modules (这些模块已有完整路径，不添加前缀)
api_router.include_router(collaborations.router, prefix="/api/v1", tags=["多智能体协作"])
api_router.include_router(tasks.router, prefix="/api/v1", tags=["任务管理"])
api_router.include_router(system_monitor.router, prefix="/api/v1", tags=["系统监控"])
api_router.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])

# Optimization modules
api_router.include_router(skill_optimization.router, prefix="/api/v1", tags=["Skill 优化"])
api_router.include_router(mcp_optimization.router, prefix="/api/v1", tags=["MCP 优化"])
api_router.include_router(dialogue_enhancement.router, tags=["对话增强"])
api_router.include_router(conversation_enhancement.router, prefix="/api/v1", tags=["会话增强"])

# Batch operations
api_router.include_router(batch_install.router, tags=["批量安装"])
api_router.include_router(skill_reuse.router, tags=["Skill 复用"])
api_router.include_router(mcp_batch.router, tags=["MCP 批量安装"])

# Backup & Recovery
api_router.include_router(backup.router, prefix="/api/v1", tags=["备份与恢复"])
api_router.include_router(backup_enhanced.router, tags=["各智能体备份与恢复(增强)"])

# Memory
api_router.include_router(memory.router, tags=["记忆管理"])

# Model Templates (包含内部路由 /model-templates)
api_router.include_router(model_templates.router, tags=["模型配置模板"])

# Monitoring & Ops
api_router.include_router(monitoring.router, tags=["监控看板"])
api_router.include_router(ops.router, tags=["智能体自动化运维"])
api_router.include_router(health.router, tags=["各智能体健康监控"])

# Audit & Scheduler
api_router.include_router(audit.router, tags=["操作审计"])
api_router.include_router(scheduler.router, tags=["全局定时调度器"])
api_router.include_router(tokens.router, tags=["Token 使用管理"])

# Workflow Engine
api_router.include_router(workflows.router, prefix="/api/v1/workflows", tags=["DAG工作流引擎"])

# Chat
api_router.include_router(chat.router, prefix="/api/v1/chat", tags=["对话补全"])

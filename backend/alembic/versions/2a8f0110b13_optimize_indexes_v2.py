"""optimize_indexes_v2

补充缺失的关键索引以提升查询性能

Revision ID: 2a8f0110b13
Revises: 03a8f0110b12
Create Date: 2026-07-28 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2a8f0110b13'
down_revision: Union[str, None] = '03a8f0110b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # users - 角色/活跃度筛选
    # ============================================================
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)

    # ============================================================
    # agents - 常用复合查询
    # ============================================================
    op.create_index(op.f('ix_agents_workspace_id_status'), 'agents', ['workspace_id', 'status'], unique=False)
    op.create_index(op.f('ix_agents_created_by_status'), 'agents', ['created_by', 'status'], unique=False)
    op.create_index(op.f('ix_agents_model_provider'), 'agents', ['model_provider'], unique=False)
    op.create_index(op.f('ix_agents_created_at'), 'agents', ['created_at'], unique=False)

    # ============================================================
    # model_config_templates - 模型提供商/名称筛选
    # ============================================================
    op.create_index(op.f('ix_model_config_templates_provider'), 'model_config_templates', ['provider'], unique=False)
    op.create_index(op.f('ix_model_config_templates_provider_model'), 'model_config_templates', ['provider', 'model'], unique=False)
    op.create_index(op.f('ix_model_config_templates_created_by'), 'model_config_templates', ['created_by'], unique=False)

    # ============================================================
    # conversations - 复合查询 + 排序
    # ============================================================
    op.create_index(op.f('ix_conversations_status'), 'conversations', ['status'], unique=False)
    op.create_index(op.f('ix_conversations_agent_id_user_id'), 'conversations', ['agent_id', 'user_id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id_updated_at'), 'conversations', ['user_id', 'updated_at'], unique=False)

    # ============================================================
    # messages - 按时间顺序遍历
    # ============================================================
    op.create_index(op.f('ix_messages_conversation_id_created_at'), 'messages', ['conversation_id', 'created_at'], unique=False)

    # ============================================================
    # workspace_members - 唯一约束 + 复合查询
    # ============================================================
    op.create_unique_constraint('uq_workspace_members', 'workspace_members', ['workspace_id', 'user_id'])
    op.create_index(op.f('ix_workspace_members_workspace_id_role'), 'workspace_members', ['workspace_id', 'role'], unique=False)

    # ============================================================
    # workspaces - 活跃筛选
    # ============================================================
    op.create_index(op.f('ix_workspaces_is_active'), 'workspaces', ['is_active'], unique=False)

    # ============================================================
    # skills - 分类/类型筛选 + 版本唯一性
    # ============================================================
    op.create_index(op.f('ix_skills_type'), 'skills', ['type'], unique=False)
    op.create_index(op.f('ix_skills_category'), 'skills', ['category'], unique=False)
    op.create_index(op.f('ix_skills_enabled'), 'skills', ['enabled'], unique=False)
    op.create_unique_constraint('uq_skills_name_version', 'skills', ['name', 'version'])

    # ============================================================
    # skill_bindings - 唯一约束(避免重复绑定)
    # ============================================================
    op.create_unique_constraint('uq_skill_bindings_agent_skill', 'skill_bindings', ['agent_id', 'skill_id'])
    op.create_index(op.f('ix_skill_bindings_enabled'), 'skill_bindings', ['enabled'], unique=False)

    # ============================================================
    # mcp_servers - 状态/名称筛选
    # ============================================================
    op.create_index(op.f('ix_mcp_servers_status'), 'mcp_servers', ['status'], unique=False)
    op.create_index(op.f('ix_mcp_servers_name'), 'mcp_servers', ['name'], unique=False)
    op.create_index(op.f('ix_mcp_servers_health_status'), 'mcp_servers', ['health_status'], unique=False)

    # ============================================================
    # operation_logs - 审计查询常用维度
    # ============================================================
    op.create_index(op.f('ix_operation_logs_action'), 'operation_logs', ['action'], unique=False)
    op.create_index(op.f('ix_operation_logs_resource_type'), 'operation_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_operation_logs_user_id_action'), 'operation_logs', ['user_id', 'action'], unique=False)
    op.create_index(op.f('ix_operation_logs_resource_type_resource_id'), 'operation_logs', ['resource_type', 'resource_id'], unique=False)


def downgrade() -> None:
    # operation_logs
    op.drop_index(op.f('ix_operation_logs_resource_type_resource_id'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_user_id_action'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_resource_type'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_action'), table_name='operation_logs')

    # mcp_servers
    op.drop_index(op.f('ix_mcp_servers_health_status'), table_name='mcp_servers')
    op.drop_index(op.f('ix_mcp_servers_name'), table_name='mcp_servers')
    op.drop_index(op.f('ix_mcp_servers_status'), table_name='mcp_servers')

    # skill_bindings
    op.drop_index(op.f('ix_skill_bindings_enabled'), table_name='skill_bindings')
    op.drop_constraint('uq_skill_bindings_agent_skill', 'skill_bindings', type_='unique')

    # skills
    op.drop_constraint('uq_skills_name_version', 'skills', type_='unique')
    op.drop_index(op.f('ix_skills_enabled'), table_name='skills')
    op.drop_index(op.f('ix_skills_category'), table_name='skills')
    op.drop_index(op.f('ix_skills_type'), table_name='skills')

    # workspaces
    op.drop_index(op.f('ix_workspaces_is_active'), table_name='workspaces')

    # workspace_members
    op.drop_index(op.f('ix_workspace_members_workspace_id_role'), table_name='workspace_members')
    op.drop_constraint('uq_workspace_members', 'workspace_members', type_='unique')

    # messages
    op.drop_index(op.f('ix_messages_conversation_id_created_at'), table_name='messages')

    # conversations
    op.drop_index(op.f('ix_conversations_user_id_updated_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_agent_id_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_status'), table_name='conversations')

    # model_config_templates
    op.drop_index(op.f('ix_model_config_templates_created_by'), table_name='model_config_templates')
    op.drop_index(op.f('ix_model_config_templates_provider_model'), table_name='model_config_templates')
    op.drop_index(op.f('ix_model_config_templates_provider'), table_name='model_config_templates')

    # agents
    op.drop_index(op.f('ix_agents_created_at'), table_name='agents')
    op.drop_index(op.f('ix_agents_model_provider'), table_name='agents')
    op.drop_index(op.f('ix_agents_created_by_status'), table_name='agents')
    op.drop_index(op.f('ix_agents_workspace_id_status'), table_name='agents')

    # users
    op.drop_index(op.f('ix_users_is_active'), table_name='users')
    op.drop_index(op.f('ix_users_role'), table_name='users')

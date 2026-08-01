"""add missing tables v3

Revision ID: 03a8f0110b13
Revises: 2a8f0110b13
Create Date: 2026-07-31

补充缺失的数据表，对齐ORM模型与数据库结构
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03a8f0110b13'
down_revision: Union[str, None] = '2a8f0110b13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # Model Template Version (模型模板版本历史)
    # ============================================================
    op.create_table('model_template_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('change_log', sa.String(length=500), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'version', name='uq_model_template_versions_template_version')
    )
    op.create_index(op.f('ix_model_template_versions_template_id'), 'model_template_versions', ['template_id'], unique=False)

    # ============================================================
    # Model Template Binding (模板-智能体绑定)
    # ============================================================
    op.create_table('model_template_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('override_config', sa.Text(), nullable=True),
        sa.Column('override_model', sa.String(length=100), nullable=True),
        sa.Column('override_provider', sa.String(length=50), nullable=True),
        sa.Column('sync_mode', sa.String(length=20), server_default='auto', nullable=True),
        sa.Column('gray_percentage', sa.Integer(), server_default='100', nullable=True),
        sa.Column('gray_status', sa.String(length=20), server_default='synced', nullable=True),
        sa.Column('gray_synced_version', sa.Integer(), nullable=True),
        sa.Column('gray_error', sa.String(length=500), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'agent_id', name='uq_model_template_bindings_template_agent')
    )
    op.create_index(op.f('ix_model_template_bindings_template_id'), 'model_template_bindings', ['template_id'], unique=False)
    op.create_index(op.f('ix_model_template_bindings_agent_id'), 'model_template_bindings', ['agent_id'], unique=False)

    # ============================================================
    # Token Usage & Budget (Token用量与预算管理)
    # ============================================================
    op.create_table('token_usages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('conversation_id', sa.String(length=36), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('output_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('cached_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('compressed_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('cost', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('usage_date', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_usages_user_id'), 'token_usages', ['user_id'], unique=False)
    op.create_index(op.f('ix_token_usages_agent_id'), 'token_usages', ['agent_id'], unique=False)
    op.create_index(op.f('ix_token_usages_conversation_id'), 'token_usages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_token_usages_model_name'), 'token_usages', ['model_name'], unique=False)
    op.create_index(op.f('ix_token_usages_usage_date'), 'token_usages', ['usage_date'], unique=False)

    op.create_table('token_budgets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('monthly_budget', sa.Float(), server_default='10.0', nullable=True),
        sa.Column('token_quota', sa.Integer(), server_default='10000000', nullable=True),
        sa.Column('alert_threshold', sa.Integer(), server_default='80', nullable=True),
        sa.Column('block_when_exceeded', sa.Boolean(), server_default='False', nullable=True),
        sa.Column('cascade_enabled', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('cascade_chain', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_token_budgets_user_id')
    )
    op.create_index(op.f('ix_token_budgets_user_id'), 'token_budgets', ['user_id'], unique=False)

    op.create_table('token_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('alert_type', sa.String(length=32), nullable=True),
        sa.Column('severity', sa.String(length=16), server_default='warning', nullable=True),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('threshold_pct', sa.Integer(), nullable=True),
        sa.Column('current_usage', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=16), server_default='open', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_alerts_user_id'), 'token_alerts', ['user_id'], unique=False)

    op.create_table('model_cascade_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('task_type', sa.String(length=32), nullable=True),
        sa.Column('primary_model', sa.String(length=100), nullable=True),
        sa.Column('fallback_chain', sa.Text(), nullable=True),
        sa.Column('max_input_tokens', sa.Integer(), server_default='8000', nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_type', name='uq_model_cascade_rules_task_type')
    )
    op.create_index(op.f('ix_model_cascade_rules_task_type'), 'model_cascade_rules', ['task_type'], unique=False)

    op.create_table('token_optimization_stats',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('usage_date', sa.String(length=10), nullable=True),
        sa.Column('total_input', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_output', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_cost', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('cached_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('compressed_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('cascade_saved_cost', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_optimization_stats_usage_date'), 'token_optimization_stats', ['usage_date'], unique=False)

    # ============================================================
    # Agent Memory (智能体记忆)
    # ============================================================
    op.create_table('agent_memories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('memory_type', sa.String(length=20), server_default='long_term', nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('category', sa.String(length=30), server_default='conversation', nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('embedding_text', sa.Text(), nullable=True),
        sa.Column('embedding_vector_id', sa.String(length=100), nullable=True),
        sa.Column('importance_score', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('access_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_forgotten', sa.Boolean(), server_default='False', nullable=True),
        sa.Column('forget_reason', sa.String(length=100), nullable=True),
        sa.Column('forgotten_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ttl_seconds', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_sensitive', sa.Boolean(), server_default='False', nullable=True),
        sa.Column('sensitive_info_type', sa.String(length=50), nullable=True),
        sa.Column('masked_content', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('shared_to_agents', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default='False', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_memories_agent_id'), 'agent_memories', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_memories_memory_type'), 'agent_memories', ['memory_type'], unique=False)
    op.create_index(op.f('ix_agent_memories_category'), 'agent_memories', ['category'], unique=False)
    op.create_index(op.f('ix_agent_memories_importance_score'), 'agent_memories', ['importance_score'], unique=False)

    op.create_table('memory_analytics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=True),
        sa.Column('total_memories', sa.Integer(), server_default='0', nullable=True),
        sa.Column('short_term_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('long_term_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('shared_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('forgotten_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('merged_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('category_distribution', sa.Text(), nullable=True),
        sa.Column('avg_importance', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('high_importance_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('medium_importance_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('low_importance_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_analytics_agent_id'), 'memory_analytics', ['agent_id'], unique=False)

    # ============================================================
    # Audit Logs (审计日志增强)
    # ============================================================
    op.create_table('audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=32), nullable=False),
        sa.Column('resource_id', sa.String(length=128), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('prev_hash', sa.String(length=64), nullable=True),
        sa.Column('curr_hash', sa.String(length=64), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_workspace_id'), 'audit_logs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_recorded_at'), 'audit_logs', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id_action'), 'audit_logs', ['user_id', 'action'], unique=False)

    op.create_table('audit_archives',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('original_log_id', sa.String(length=36), nullable=True),
        sa.Column('archive_date', sa.String(length=10), nullable=True),
        sa.Column('archive_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('archive_path', sa.String(length=500), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('audit_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('rule_type', sa.String(length=32), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ============================================================
    # Backup Records (备份恢复)
    # ============================================================
    op.create_table('backup_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('backup_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='running', nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('encrypted', sa.Boolean(), server_default='False', nullable=True),
        sa.Column('included_components', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backup_records_workspace_id'), 'backup_records', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_backup_records_status'), 'backup_records', ['status'], unique=False)
    op.create_index(op.f('ix_backup_records_created_at'), 'backup_records', ['created_at'], unique=False)

    op.create_table('backup_policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('schedule', sa.String(length=50), nullable=True),
        sa.Column('retention_days', sa.Integer(), server_default='30', nullable=True),
        sa.Column('components', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('restore_operations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('backup_id', sa.String(length=36), nullable=True),
        sa.Column('restore_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('encryption_keys',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('key_name', sa.String(length=100), nullable=True),
        sa.Column('key_material', sa.Text(), nullable=True),
        sa.Column('algorithm', sa.String(length=32), server_default='AES-256-GCM', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_name', name='uq_encryption_keys_key_name')
    )

    # ============================================================
    # Health Checks (健康检查)
    # ============================================================
    op.create_table('health_check_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('check_level', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_check_runs_agent_id'), 'health_check_runs', ['agent_id'], unique=False)
    op.create_index(op.f('ix_health_check_runs_checked_at'), 'health_check_runs', ['checked_at'], unique=False)

    op.create_table('health_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_snapshots_agent_id'), 'health_snapshots', ['agent_id'], unique=False)
    op.create_index(op.f('ix_health_snapshots_snapshot_time'), 'health_snapshots', ['snapshot_time'], unique=False)

    op.create_table('agent_health_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('check_interval_minutes', sa.Integer(), server_default='5', nullable=True),
        sa.Column('alert_threshold', sa.Float(), server_default='60.0', nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', name='uq_agent_health_configs_agent_id')
    )

    # ============================================================
    # Collaboration Tasks (多Agent协作)
    # ============================================================
    op.create_table('collaboration_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mode', sa.String(length=32), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=True),
        sa.Column('progress', sa.Integer(), server_default='0', nullable=True),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collaboration_tasks_workspace_id'), 'collaboration_tasks', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_collaboration_tasks_status'), 'collaboration_tasks', ['status'], unique=False)

    op.create_table('collaboration_agents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collaboration_agents_task_id'), 'collaboration_agents', ['task_id'], unique=False)

    # ============================================================
    # Notification Config (通知配置)
    # ============================================================
    op.create_table('notification_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('notify_method', sa.String(length=16), server_default='both', nullable=True),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('smtp_host', sa.String(length=255), nullable=True),
        sa.Column('smtp_port', sa.Integer(), server_default='465', nullable=True),
        sa.Column('smtp_user', sa.String(length=255), nullable=True),
        sa.Column('smtp_password', sa.String(length=255), nullable=True),
        sa.Column('smtp_use_ssl', sa.Boolean(), server_default='True', nullable=True),
        sa.Column('smtp_from', sa.String(length=255), nullable=True),
        sa.Column('default_recipients', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    print("✅ 已完成所有缺失表的创建")


def downgrade() -> None:
    # 按依赖关系反向删除
    op.drop_table('notification_configs')
    op.drop_table('collaboration_agents')
    op.drop_table('collaboration_tasks')
    op.drop_table('agent_health_configs')
    op.drop_table('health_snapshots')
    op.drop_table('health_check_runs')
    op.drop_table('encryption_keys')
    op.drop_table('restore_operations')
    op.drop_table('backup_policies')
    op.drop_table('backup_records')
    op.drop_table('audit_rules')
    op.drop_table('audit_archives')
    op.drop_table('audit_logs')
    op.drop_table('memory_analytics')
    op.drop_table('agent_memories')
    op.drop_table('token_optimization_stats')
    op.drop_table('model_cascade_rules')
    op.drop_table('token_alerts')
    op.drop_table('token_budgets')
    op.drop_table('token_usages')
    op.drop_table('model_template_bindings')
    op.drop_table('model_template_versions')
    print("✅ 已回滚所有新增表")

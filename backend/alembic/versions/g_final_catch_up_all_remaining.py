"""catch up: create all remaining model tables not yet in migrations

Revision ID: g_catchup01
Revises: f5879606c97b
Create Date: 2026-08-06 00:00:00.000000

Missing tables:
  1. event_logs           — Event Bus 事件日志
  2. dead_letter_queue    — 死信队列
  3. workflows            — DAG 工作流定义
  4. workflow_nodes       — 工作流节点
  5. workflow_edges       — 工作流边(依赖)
  6. workflow_executions  — 工作流执行记录
  7. audit_logs_partitioned — 审计日志分区版
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g_catchup01'
down_revision: Union[str, None] = 'f5879606c97b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. event_logs ──────────────────────────────────────────
    op.create_table(
        'event_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(128), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(64), server_default='system'),
        sa.Column('priority', sa.String(16), server_default='normal'),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('correlation_id', sa.String(36), nullable=True),
        sa.Column('delivered', sa.Boolean(), server_default='false'),
        sa.Column('delivery_attempts', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_event_logs_event_type', 'event_logs', ['event_type'])
    op.create_index('ix_event_logs_source', 'event_logs', ['source'])
    op.create_index('ix_event_logs_timestamp', 'event_logs', ['timestamp'])
    op.create_index('ix_event_logs_correlation_id', 'event_logs', ['correlation_id'])

    # ── 2. dead_letter_queue ───────────────────────────────────
    op.create_table(
        'dead_letter_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('original_event_id', sa.String(36), nullable=True),
        sa.Column('event_type', sa.String(128), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(64), server_default='system'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('max_retries', sa.Integer(), server_default='3'),
        sa.Column('status', sa.String(16), server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_dead_letter_queue_original_event_id', 'dead_letter_queue', ['original_event_id'])
    op.create_index('ix_dead_letter_queue_event_type', 'dead_letter_queue', ['event_type'])

    # ── 3. workflows ───────────────────────────────────────────
    op.create_table(
        'workflows',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('dag_config', sa.Text(), server_default='{}'),
        sa.Column('variables', sa.Text(), server_default='{}'),
        sa.Column('timeout', sa.Integer(), server_default='3600'),
        sa.Column('max_retries', sa.Integer(), server_default='2'),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('workspace_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.Text(), server_default='{}'),
    )

    # ── 4. workflow_nodes ──────────────────────────────────────
    op.create_table(
        'workflow_nodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('node_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('node_type', sa.String(50), nullable=False),
        sa.Column('agent_id', sa.String(36), nullable=True),
        sa.Column('config', sa.Text(), server_default='{}'),
        sa.Column('input_mapping', sa.Text(), server_default='{}'),
        sa.Column('output_key', sa.String(200), server_default=''),
        sa.Column('timeout', sa.Integer(), server_default='300'),
        sa.Column('retries', sa.Integer(), server_default='0'),
        sa.Column('retry_delay', sa.Integer(), server_default='5'),
        sa.Column('condition', sa.Text(), server_default=''),
        sa.Column('order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_workflow_nodes_workflow_id', 'workflow_nodes', ['workflow_id'])

    # ── 5. workflow_edges ──────────────────────────────────────
    op.create_table(
        'workflow_edges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('source_node_id', sa.String(100), nullable=False),
        sa.Column('target_node_id', sa.String(100), nullable=False),
        sa.Column('condition', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_workflow_edges_workflow_id', 'workflow_edges', ['workflow_id'])

    # ── 6. workflow_executions ─────────────────────────────────
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(20), server_default='running'),
        sa.Column('trigger', sa.String(50), server_default='manual'),
        sa.Column('input_data', sa.Text(), server_default='{}'),
        sa.Column('output_data', sa.Text(), server_default='{}'),
        sa.Column('node_results', sa.Text(), server_default='{}'),
        sa.Column('error_message', sa.Text(), server_default=''),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_workflow_executions_workflow_id', 'workflow_executions', ['workflow_id'])

    # ── 7. audit_logs_partitioned ──────────────────────────────
    # 注意: 生产环境应使用 PostgreSQL 原生分区表
    # CREATE TABLE audit_logs_partitioned (...) PARTITION BY RANGE (partition_date);
    # 此处先创建普通表以兼容开发环境
    op.create_table(
        'audit_logs_partitioned',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('partition_date', sa.Date(), nullable=False),
        sa.Column('operator_id', sa.String(64), nullable=False),
        sa.Column('operator_ip', sa.String(64), server_default=''),
        sa.Column('action_type', sa.String(64), nullable=False),
        sa.Column('target_id', sa.String(128), server_default=''),
        sa.Column('target_type', sa.String(64), server_default=''),
        sa.Column('details', sa.Text(), server_default=''),
        sa.Column('result', sa.String(16), server_default='success'),
        sa.Column('device_info', sa.Text(), server_default=''),
        sa.Column('trace_id', sa.String(64), server_default=''),
        sa.Column('geo_ip', sa.String(64), server_default=''),
        sa.Column('prev_hash', sa.String(64), server_default=''),
        sa.Column('curr_hash', sa.String(64), server_default=''),
        sa.Column('workspace_id', sa.String(36), server_default=''),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_audit_partition_date', 'audit_logs_partitioned', ['partition_date'])
    op.create_index('idx_audit_operator', 'audit_logs_partitioned', ['operator_id'])
    op.create_index('idx_audit_action', 'audit_logs_partitioned', ['action_type'])
    op.create_index('idx_audit_target', 'audit_logs_partitioned', ['target_id'])
    op.create_index('idx_audit_trace', 'audit_logs_partitioned', ['trace_id'])


def downgrade() -> None:
    op.drop_table('audit_logs_partitioned')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_edges')
    op.drop_table('workflow_nodes')
    op.drop_table('workflows')
    op.drop_table('dead_letter_queue')
    op.drop_table('event_logs')

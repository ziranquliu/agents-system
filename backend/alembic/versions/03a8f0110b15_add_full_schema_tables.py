"""add full schema tables (auto-generated)

Revision ID: 03a8f0110b15
Revises: 03a8f0110b14
Create Date: 2026-08-03
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "03a8f0110b15"
down_revision = "03a8f0110b14"


def upgrade() -> None:
    op.execute("""CREATE TABLE agent_deployments (
	id VARCHAR(36) NOT NULL, 
	agent_name VARCHAR(255) NOT NULL, 
	version VARCHAR(64), 
	template_yaml TEXT, 
	parameters TEXT, 
	status VARCHAR(32), 
	health_score FLOAT, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	deployed_at TIMESTAMP WITHOUT TIME ZONE, 
	rolled_back_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(255), 
	is_active BOOLEAN, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE agent_metrics (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(36) NOT NULL, 
	agent_name VARCHAR(100), 
	qps FLOAT, 
	success_rate FLOAT, 
	latency_p50 FLOAT, 
	latency_p95 FLOAT, 
	latency_p99 FLOAT, 
	memory_mb FLOAT, 
	cpu_percent FLOAT, 
	health_score FLOAT, 
	recorded_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE alert_configs (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	priority VARCHAR(10), 
	metric_name VARCHAR(50) NOT NULL, 
	operator VARCHAR(10) NOT NULL, 
	threshold FLOAT NOT NULL, 
	duration_seconds INTEGER, 
	target_type VARCHAR(20), 
	target_agent_id VARCHAR(36), 
	notify_method VARCHAR(50), 
	notify_target VARCHAR(200), 
	enabled BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE alert_records (
	id VARCHAR(36) NOT NULL, 
	config_id VARCHAR(36), 
	alert_name VARCHAR(100), 
	priority VARCHAR(10), 
	agent_id VARCHAR(36), 
	metric_name VARCHAR(50), 
	current_value FLOAT, 
	threshold FLOAT, 
	operator VARCHAR(10), 
	status VARCHAR(20), 
	acknowledged_by VARCHAR(36), 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	fired_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE audit_alerts (
	id VARCHAR(36) NOT NULL, 
	alert_type VARCHAR(32), 
	severity VARCHAR(16), 
	operator_id VARCHAR(128), 
	description TEXT, 
	evidence TEXT, 
	status VARCHAR(16), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE audit_configs (
	id VARCHAR(36) NOT NULL, 
	retention_days INTEGER, 
	archive_after_days INTEGER, 
	rotation_size_mb INTEGER, 
	siem_enabled BOOLEAN, 
	siem_host VARCHAR(255), 
	siem_port INTEGER, 
	siem_protocol VARCHAR(16), 
	mask_sensitive BOOLEAN, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE backup_event_logs (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	event_type VARCHAR(128), 
	event_meta TEXT, 
	backup_id VARCHAR(255), 
	triggered_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(16), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE batch_install_items (
	id VARCHAR(36) NOT NULL, 
	queue_id VARCHAR(36) NOT NULL, 
	skill_id VARCHAR(36) NOT NULL, 
	skill_name VARCHAR(100), 
	agent_id VARCHAR(36) NOT NULL, 
	agent_name VARCHAR(100), 
	dep_check_status VARCHAR(20), 
	dep_check_detail TEXT, 
	status VARCHAR(20), 
	error_message TEXT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE batch_install_queues (
	id VARCHAR(36) NOT NULL, 
	operation VARCHAR(20) NOT NULL, 
	status VARCHAR(20), 
	total_items INTEGER, 
	success_count INTEGER, 
	fail_count INTEGER, 
	warn_count INTEGER, 
	precheck_status VARCHAR(20), 
	precheck_summary TEXT, 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE collaborations (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	mode VARCHAR(20), 
	status VARCHAR(20), 
	context TEXT, 
	result TEXT, 
	created_by VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE component_scans (
	id VARCHAR(36) NOT NULL, 
	status VARCHAR(20), 
	summary TEXT, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	triggered_by VARCHAR(36), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE dashboard_panels (
	id VARCHAR(36) NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	chart_type VARCHAR(30), 
	metric_names TEXT, 
	agent_ids TEXT, 
	position_x INTEGER, 
	position_y INTEGER, 
	width INTEGER, 
	height INTEGER, 
	config TEXT, 
	enabled BOOLEAN, 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE dialogue_ratings (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	message_id VARCHAR(36), 
	satisfaction_score INTEGER, 
	relevance_score INTEGER, 
	accuracy_score INTEGER, 
	completeness_score INTEGER, 
	clarity_score INTEGER, 
	speed_score INTEGER, 
	overall_score FLOAT, 
	feedback_text TEXT, 
	feedback_category VARCHAR(30), 
	rated_by VARCHAR(36), 
	rated_by_type VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE heal_rules (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	anomaly_type VARCHAR(255), 
	consecutive_threshold INTEGER, 
	error_rate_threshold FLOAT, 
	p99_latency_threshold_ms FLOAT, 
	health_drop_threshold FLOAT, 
	heal_level VARCHAR(32), 
	auto_heal BOOLEAN, 
	enabled BOOLEAN, 
	cooldown_seconds INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE health_events (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	agent_name VARCHAR(255), 
	event_type VARCHAR(128), 
	level VARCHAR(32), 
	message TEXT, 
	score_before FLOAT, 
	score_after FLOAT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE health_score_weights (
	id VARCHAR(36) NOT NULL, 
	template_name VARCHAR(255) NOT NULL, 
	description TEXT, 
	weight_response_time FLOAT, 
	weight_token FLOAT, 
	weight_error_rate FLOAT, 
	weight_session_success FLOAT, 
	weight_dependency FLOAT, 
	threshold_p95_warn_ms FLOAT, 
	threshold_p95_critical_ms FLOAT, 
	threshold_error_rate_warn FLOAT, 
	threshold_error_rate_critical FLOAT, 
	threshold_session_success_warn FLOAT, 
	threshold_session_success_critical FLOAT, 
	apply_agents TEXT, 
	is_default BOOLEAN, 
	enabled BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE health_trend_points (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	score FLOAT NOT NULL, 
	bucket_minute TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE human_interventions (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	message_id VARCHAR(36), 
	agent_id VARCHAR(36) NOT NULL, 
	intervention_type VARCHAR(20) NOT NULL, 
	original_content TEXT, 
	original_metadata TEXT, 
	modified_content TEXT, 
	modified_metadata TEXT, 
	approved BOOLEAN, 
	approval_note TEXT, 
	handled_by VARCHAR(36), 
	handled_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE knowledge_bases (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	icon VARCHAR(10), 
	document_count INTEGER, 
	chunk_count INTEGER, 
	status VARCHAR(20), 
	created_by VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE log_collection_configs (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	log_level VARCHAR(16), 
	sources TEXT, 
	rotation_size_mb INTEGER, 
	rotation_interval_days INTEGER, 
	retention_days INTEGER, 
	enabled BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (agent_id)
)""")
    op.execute("""CREATE TABLE log_entries (
	id VARCHAR(36) NOT NULL, 
	timestamp TIMESTAMP WITHOUT TIME ZONE, 
	level VARCHAR(16), 
	logger VARCHAR(255), 
	message TEXT, 
	source_type VARCHAR(32), 
	source_id VARCHAR(255), 
	agent_id VARCHAR(255), 
	trace_id VARCHAR(255), 
	log_metadata TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE maintenance_executions (
	id VARCHAR(36) NOT NULL, 
	task_id VARCHAR(255), 
	task_type VARCHAR(32), 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(16), 
	items_processed INTEGER, 
	items_cleaned INTEGER, 
	error_message TEXT, 
	duration_seconds FLOAT, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE maintenance_tasks (
	id VARCHAR(36) NOT NULL, 
	task_type VARCHAR(32), 
	name VARCHAR(255), 
	description TEXT, 
	cron_expression VARCHAR(64), 
	enabled BOOLEAN, 
	maintenance_window_start VARCHAR(8), 
	maintenance_window_end VARCHAR(8), 
	timeout_seconds INTEGER, 
	last_run_at TIMESTAMP WITHOUT TIME ZONE, 
	last_run_result TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE mcp_agent_bindings (
	id VARCHAR(36) NOT NULL, 
	mcp_server_id VARCHAR(36) NOT NULL, 
	mcp_server_name VARCHAR(100), 
	agent_id VARCHAR(36) NOT NULL, 
	agent_name VARCHAR(100), 
	sync_mode VARCHAR(20), 
	override_config TEXT, 
	override_protocol VARCHAR(20), 
	override_auth TEXT, 
	template_id VARCHAR(36), 
	status VARCHAR(20), 
	source_version VARCHAR(20), 
	synced_version VARCHAR(20), 
	is_encrypted BOOLEAN, 
	encryption_method VARCHAR(20), 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	sync_error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE mcp_batch_install_items (
	id VARCHAR(36) NOT NULL, 
	queue_id VARCHAR(36) NOT NULL, 
	mcp_server_id VARCHAR(36) NOT NULL, 
	mcp_server_name VARCHAR(100), 
	agent_id VARCHAR(36) NOT NULL, 
	sync_mode VARCHAR(20), 
	status VARCHAR(20), 
	error_message TEXT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE mcp_batch_install_queues (
	id VARCHAR(36) NOT NULL, 
	status VARCHAR(20), 
	total_items INTEGER, 
	success_count INTEGER, 
	fail_count INTEGER, 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE ops_reports (
	id VARCHAR(36) NOT NULL, 
	report_type VARCHAR(16), 
	title VARCHAR(255), 
	period_start TIMESTAMP WITHOUT TIME ZONE, 
	period_end TIMESTAMP WITHOUT TIME ZONE, 
	availability_rate FLOAT, 
	total_requests INTEGER, 
	error_count INTEGER, 
	anomaly_count INTEGER, 
	heal_count INTEGER, 
	scaling_events INTEGER, 
	maintenance_executions INTEGER, 
	top_agents TEXT, 
	resource_trends TEXT, 
	suggestions TEXT, 
	raw_data TEXT, 
	generated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by VARCHAR(255), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE rating_analytics (
	id VARCHAR(36) NOT NULL, 
	period VARCHAR(20), 
	total_ratings INTEGER, 
	avg_satisfaction FLOAT, 
	avg_relevance FLOAT, 
	avg_accuracy FLOAT, 
	avg_completeness FLOAT, 
	avg_clarity FLOAT, 
	avg_speed FLOAT, 
	avg_overall FLOAT, 
	satisfaction_distribution TEXT, 
	category_distribution TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE restore_drills (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	agent_name VARCHAR(255), 
	backup_id VARCHAR(255), 
	status VARCHAR(16), 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	restore_ok BOOLEAN, 
	duration_seconds FLOAT, 
	report_data TEXT, 
	error_message TEXT, 
	created_by VARCHAR(255), 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE scaling_events (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	agent_name VARCHAR(255), 
	direction VARCHAR(32), 
	previous_instances INTEGER, 
	new_instances INTEGER, 
	trigger_reason TEXT, 
	metric_value FLOAT, 
	success BOOLEAN, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE scaling_policies (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	agent_name VARCHAR(255), 
	enabled BOOLEAN, 
	metric_type VARCHAR(32), 
	scale_out_threshold FLOAT, 
	scale_in_threshold FLOAT, 
	min_instances INTEGER, 
	max_instances INTEGER, 
	scale_out_cooldown INTEGER, 
	scale_in_cooldown INTEGER, 
	scale_out_step INTEGER, 
	scale_in_step INTEGER, 
	scheduled_scale_out TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE scanner_alerts (
	id VARCHAR(36) NOT NULL, 
	component_type VARCHAR(20), 
	component_id VARCHAR(36), 
	component_name VARCHAR(200), 
	previous_status VARCHAR(20), 
	current_status VARCHAR(20), 
	severity VARCHAR(16), 
	message TEXT, 
	scan_id VARCHAR(36), 
	status VARCHAR(16), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE self_heal_records (
	id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(255), 
	agent_name VARCHAR(255), 
	anomaly_type VARCHAR(255), 
	anomaly_value FLOAT, 
	threshold_value FLOAT, 
	consecutive_count INTEGER, 
	heal_level VARCHAR(32), 
	status VARCHAR(32), 
	action_taken TEXT, 
	health_score_before FLOAT, 
	health_score_after FLOAT, 
	verified BOOLEAN, 
	error_message TEXT, 
	detected_at TIMESTAMP WITHOUT TIME ZONE, 
	healed_at TIMESTAMP WITHOUT TIME ZONE, 
	duration_seconds FLOAT, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE skill_reuse_relations (
	id VARCHAR(36) NOT NULL, 
	source_skill_id VARCHAR(36) NOT NULL, 
	source_skill_name VARCHAR(100), 
	source_agent_id VARCHAR(36), 
	target_skill_id VARCHAR(36) NOT NULL, 
	target_skill_name VARCHAR(100), 
	target_agent_id VARCHAR(36) NOT NULL, 
	reuse_mode VARCHAR(20) NOT NULL, 
	sync_mode VARCHAR(20), 
	status VARCHAR(20), 
	source_version VARCHAR(20), 
	target_version VARCHAR(20), 
	synced_version VARCHAR(20), 
	last_notified_at TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	reuse_count INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE tasks (
	id VARCHAR(36) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	description TEXT, 
	status VARCHAR(20), 
	priority VARCHAR(10), 
	assigned_to VARCHAR(36), 
	created_by VARCHAR(36) NOT NULL, 
	due_date TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE update_logs (
	id VARCHAR(36) NOT NULL, 
	component_type VARCHAR(20), 
	component_id VARCHAR(36), 
	component_name VARCHAR(200), 
	action VARCHAR(20), 
	old_version VARCHAR(50), 
	new_version VARCHAR(50), 
	compatibility VARCHAR(20), 
	detail TEXT, 
	status VARCHAR(20), 
	created_by VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE update_snapshots (
	id VARCHAR(36) NOT NULL, 
	component_type VARCHAR(20), 
	component_id VARCHAR(36), 
	component_name VARCHAR(200), 
	old_version VARCHAR(50), 
	new_version VARCHAR(50), 
	before_state TEXT, 
	after_state TEXT, 
	created_by VARCHAR(100), 
	rolled_back BOOLEAN, 
	rollback_time TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE component_scan_items (
	id VARCHAR(36) NOT NULL, 
	scan_id VARCHAR(36) NOT NULL, 
	component_type VARCHAR(20) NOT NULL, 
	component_id VARCHAR(36) NOT NULL, 
	component_name VARCHAR(200), 
	status VARCHAR(20), 
	error_message TEXT, 
	details TEXT, 
	scanned_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(scan_id) REFERENCES component_scans (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE knowledge_documents (
	id VARCHAR(36) NOT NULL, 
	knowledge_base_id VARCHAR(36) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	content TEXT, 
	content_type VARCHAR(20), 
	file_name VARCHAR(500), 
	file_size INTEGER, 
	chunk_count INTEGER, 
	status VARCHAR(20), 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE knowledge_chunks (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	knowledge_base_id VARCHAR(36) NOT NULL, 
	content TEXT NOT NULL, 
	chunk_metadata TEXT, 
	embedding_id VARCHAR(100), 
	embedding TEXT, 
	chunk_index INTEGER, 
	token_count INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES knowledge_documents (id) ON DELETE CASCADE, 
	FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE
)""")


def downgrade() -> None:
    tables = ["knowledge_chunks", "knowledge_documents", "component_scan_items", "update_snapshots", "update_logs", "tasks", "skill_reuse_relations", "self_heal_records", "scanner_alerts", "scaling_policies", "scaling_events", "restore_drills", "rating_analytics", "ops_reports", "mcp_batch_install_queues", "mcp_batch_install_items", "mcp_agent_bindings", "maintenance_tasks", "maintenance_executions", "log_entries", "log_collection_configs", "knowledge_bases", "human_interventions", "health_trend_points", "health_score_weights", "health_events", "heal_rules", "dialogue_ratings", "dashboard_panels", "component_scans", "collaborations", "batch_install_queues", "batch_install_items", "backup_event_logs", "audit_configs", "audit_alerts", "alert_records", "alert_configs", "agent_metrics", "agent_deployments"]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")

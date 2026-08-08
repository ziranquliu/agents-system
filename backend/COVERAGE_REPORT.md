# 测试覆盖率报告

## 生成日期: 2026-08-07

## 总体统计

| 指标 | 值 |
|------|-----|
| 测试总数 | 289 |
| 通过 | 289 |
| 失败 | 0 |
| 总覆盖率 | 32% |
| 目标覆盖率 | ≥80% |

## 高覆盖率模块 (>60%)

| 模块 | 覆盖率 | 测试文件 |
|------|--------|----------|
| memory_enhancement_service | 91% | test_memory_enhancement.py |
| self_healing_service | 90% | test_self_healing.py |
| mcp_signature_service | 88% | test_mcp_signature.py |
| token_quota_service | 87% | test_token_quota.py |
| dialogue_enhancement_service | 86% | test_dialogue_enhancement.py |
| cross_agent_restore_service | 85% | test_services_batch3.py |
| skill_combination_service | 83% | test_services_batch2.py |
| model_benchmark_service | 80% | test_services_batch2.py |
| model_hotswap_service | 73% | test_services_batch2.py |
| websocket_monitor_service | 68% | test_services_batch3.py |
| dashboard_service | 66% | test_services_batch2.py |
| conversation_sandbox_service | 46% | test_services_batch3.py |

## 本次新增测试覆盖模块

| 模块 | 覆盖率 | 测试文件 |
|------|--------|----------|
| health_service | 42% | test_health_service.py (27 tests) |
| ops_service | 37% | test_ops_service.py (20 tests) |
| token_service | 35% | test_token_service.py (38 tests) |
| workflow_engine | 33% | test_workflow_engine.py (20 tests) |

## 需要补充测试的 0% 模块 (按行数排序)

| 模块 | 未覆盖行数 |
|------|-----------|
| session_service | 261 |
| multi_agent_routing_service | 273 |
| knowledge_chunking_service | 241 |
| siem_service | 173 |
| incremental_backup_service | 177 |
| remote_backup_service | 156 |
| data_masking_service | 153 |
| role_master_service | 148 |
| yaml_deployment_service | 168 |
| scheduled_maintenance_service | 232 |
| auto_scaling_service | 143 |
| budget_alert_service | 207 |
| model_recommendation_service | 136 |
| anomaly_detection_service | 187 |
| log_aggregation_service | 206 |
| session_export_service | 180 |
| session_recovery_service | 157 |
| notification_service | 127 |
| circuit_breaker | 198 |

## 运行命令

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 运行全部测试 + 覆盖率
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html:htmlcov

# 运行新增测试
pytest tests/test_token_service.py tests/test_health_service.py tests/test_ops_service.py tests/test_self_healing.py tests/test_workflow_engine.py -v
```

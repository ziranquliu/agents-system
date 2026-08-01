# Grafana 监控看板 — 智能体管理系统

本目录提供智能体管理系统的 Prometheus 监控看板配置。

## 文件说明

| 文件 | 说明 |
|:-----|:-----|
| `agent-system-dashboard.json` | Grafana 仪表盘配置（schemaVersion 39，兼容 Grafana 9.x / 10.x） |
| `README.md` | 本说明文件 |

## 导入步骤

1. 启动 Grafana（默认 `http://localhost:3000`），使用管理员账号登录。
2. 打开左侧菜单 **Dashboards → New → Import**。
3. 在导入页面选择一种方式：
   - **上传 JSON**：点击右上角 **Upload dashboard JSON file**，选择本目录下的 `agent-system-dashboard.json`；
   - 或直接**粘贴 JSON**：复制 `agent-system-dashboard.json` 全文，粘贴到 JSON 输入框。
4. 导入前 Grafana 会要求选择数据源：在 **Prometheus** 下拉框中选择你配置的 Prometheus 数据源（此处使用 `${DS_PROMETHEUS}` 占位，导入时可自由选择）。
5. 点击 **Import** 完成导入，即可在 **Dashboards** 列表中看到「智能体管理系统监控看板」。

## 面板清单

| 面板 | 类型 | PromQL 查询（核心） | 说明 |
|:-----|:-----|:-----|:-----|
| 健康评分概览 | Stat | `max by (agent) (agent_health_score)` | 每个 Agent 的当前健康评分（0-100，<60 红色 / <80 橙色 / ≥80 绿色） |
| 健康评分趋势 | Time series | `agent_health_score` | 健康评分随时间变化曲线（按 Agent 分组） |
| Token 用量 | Time series | `sum by (agent) (rate({__name__=~"token.*|token_usage_total|agent_token_.*"}[5m]))` | Token 消耗速率（使用通配匹配，指标名略有出入也能显示） |
| 任务成功率 | Pie chart | `avg by (agent) (agent_success_rate)` | 各 Agent 任务成功率占比（<90% 红色 / <95% 橙色） |
| 活跃告警（P0） | Stat | `sum(agent_alert_count{priority="P0"})` | 当前严重告警数量（背景色随数量变化） |
| 系统事件计数 | Stat | `sum({__name__=~"backup.*"})` / `scan.*` / `audit.*` | 备份 / 扫描 / 审计 / 告警事件计数（通配匹配） |

## 实际指标名（来自 `backend/app/services/monitoring_service.py`）

Prometheus 端点：`GET /api/v1/monitoring/prometheus`（PlainText，Prometheus text format）

| 指标名 | 类型 | 标签 | 说明 |
|:-----|:-----|:-----|:-----|
| `agent_health_score` | gauge | `agent`, `name` | Agent 健康评分（0-100） |
| `agent_qps` | gauge | `agent` | 每秒请求数 |
| `agent_success_rate` | gauge | `agent` | 任务成功率（0-100%） |
| `agent_latency_p50_ms` | gauge | `agent` | P50 延迟（毫秒） |
| `agent_latency_p95_ms` | gauge | `agent` | P95 延迟（毫秒） |
| `agent_memory_mb` | gauge | `agent` | 内存占用（MB） |
| `agent_cpu_percent` | gauge | `agent` | CPU 使用率（%） |
| `agent_alert_count` | gauge | `priority`（P0-P3） | 各优先级活跃告警数 |

> **说明**：Token 用量、备份/扫描/审计事件类指标当前可能尚未在 `/prometheus` 端点导出。
> 看板中相关面板使用了通配匹配 `{__name__=~"token.*"}`、`{__name__=~"backup.*|scan.*|audit.*"}`，
> 一旦这些指标接入 Prometheus（无论命名如何），面板将自动显示数据，无需修改看板。

## Prometheus 抓取配置示例

```yaml
scrape_configs:
  - job_name: 'agent-system'
    scrape_interval: 30s
    metrics_path: '/api/v1/monitoring/prometheus'
    static_configs:
      - targets: ['localhost:8000']   # 替换为后端实际地址
```

## 排障

- **面板显示 "No data"**：确认后端 `/api/v1/monitoring/prometheus` 端点可访问（`curl http://localhost:8000/api/v1/monitoring/prometheus`），并确认 Prometheus target 状态为 UP。
- **导入报 schemaVersion 不兼容**：本文件使用 schemaVersion 39，请使用 Grafana 9.1 及以上版本；低版本可手动在 Grafana 内新建面板后参考本文件中的查询。

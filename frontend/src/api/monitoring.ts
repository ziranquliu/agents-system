import apiFetch from './client'

export interface AgentMetrics {
  [agentId: string]: {
    agent_id: string; agent_name: string
    qps: number; success_rate: number
    latency_p50: number; latency_p95: number; latency_p99: number
    memory_mb: number; cpu_percent: number
    health_score: number; recorded_at: string | null
  }
}

export interface AlertConfig {
  id: string; name: string; description: string
  priority: string; metric_name: string
  operator: string; threshold: number
  duration_seconds: number
  target_type: string; target_agent_id: string | null
  notify_method: string; notify_target: string
  enabled: boolean; created_at: string | null
}

export interface AlertRecord {
  id: string; config_id: string; alert_name: string
  priority: string; agent_id: string
  metric_name: string; current_value: number
  threshold: number; operator: string
  status: string; acknowledged_by: string | null
  acknowledged_at: string | null; resolved_at: string | null
  fired_at: string | null
}

export interface DashboardPanel {
  id: string; title: string; chart_type: string
  metric_names: string[]; agent_ids: string[]
  position_x: number; position_y: number
  width: number; height: number
  config: Record<string, unknown>
  enabled: boolean; created_by: string | null
}

// Metrics
export async function recordMetric(data: Record<string, unknown>): Promise<{ id: string; health_score: number }> {
  const resp = await apiFetch('/api/v1/monitoring/metrics', { method: 'POST', data })
  return resp.data
}

export async function getLatestMetrics(): Promise<AgentMetrics> {
  const resp = await apiFetch('/api/v1/monitoring/metrics/latest', { method: 'GET' })
  return resp.data
}

export async function getMetricHistory(agentId: string, metricNames = 'health_score,qps,latency_p95', hours = 24, interval = 5): Promise<Record<string, Array<{ time: string; value: number }>>> {
  const resp = await apiFetch(`/api/v1/monitoring/metrics/history/${agentId}?metric_names=${encodeURIComponent(metricNames)}&hours=${hours}&interval_minutes=${interval}`, { method: 'GET' })
  return resp.data
}

export async function getAgentRanking(sortBy = 'health_score', limit = 20): Promise<Array<Record<string, unknown>>> {
  const resp = await apiFetch(`/api/v1/monitoring/metrics/ranking?sort_by=${sortBy}&limit=${limit}`, { method: 'GET' })
  return resp.data
}

// Alert configs
export async function createAlertConfig(data: Record<string, unknown>): Promise<AlertConfig> {
  const resp = await apiFetch('/api/v1/monitoring/alert-configs', { method: 'POST', data })
  return resp.data
}

export async function updateAlertConfig(id: string, data: Record<string, unknown>): Promise<AlertConfig> {
  const resp = await apiFetch(`/api/v1/monitoring/alert-configs/${id}`, { method: 'PUT', data })
  return resp.data
}

export async function listAlertConfigs(enabledOnly = false): Promise<AlertConfig[]> {
  const resp = await apiFetch(`/api/v1/monitoring/alert-configs?enabled_only=${enabledOnly}`, { method: 'GET' })
  return resp.data
}

export async function deleteAlertConfig(id: string): Promise<void> {
  await apiFetch(`/api/v1/monitoring/alert-configs/${id}`, { method: 'DELETE' })
}

// Alert records
export async function listAlerts(params: Record<string, string | number | undefined> = {}): Promise<{ data: AlertRecord[]; total: number }> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)) })
  const resp = await apiFetch(`/api/v1/monitoring/alerts?${qs}`, { method: 'GET' })
  return resp.data
}

export async function acknowledgeAlert(id: string, userId = ''): Promise<AlertRecord> {
  const resp = await apiFetch(`/api/v1/monitoring/alerts/${id}/acknowledge`, { method: 'POST', data: { user_id: userId } })
  return resp.data
}

export async function resolveAlert(id: string): Promise<AlertRecord> {
  const resp = await apiFetch(`/api/v1/monitoring/alerts/${id}/resolve`, { method: 'POST' })
  return resp.data
}

// Panels
export async function createPanel(data: Record<string, unknown>): Promise<DashboardPanel> {
  const resp = await apiFetch('/api/v1/monitoring/panels', { method: 'POST', data })
  return resp.data
}

export async function updatePanel(id: string, data: Record<string, unknown>): Promise<DashboardPanel> {
  const resp = await apiFetch(`/api/v1/monitoring/panels/${id}`, { method: 'PUT', data })
  return resp.data
}

export async function listPanels(): Promise<DashboardPanel[]> {
  const resp = await apiFetch('/api/v1/monitoring/panels', { method: 'GET' })
  return resp.data
}

export async function deletePanel(id: string): Promise<void> {
  await apiFetch(`/api/v1/monitoring/panels/${id}`, { method: 'DELETE' })
}

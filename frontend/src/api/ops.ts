import apiClient from './client';

// ==================== 4.22.1 自动部署 ====================
export const listDeployments = (params?: { skip?: number; limit?: number; status?: string; agent_name?: string }) =>
  apiClient.get('/api/v1/ops/deployments', { params });

export const createDeployment = (data: {
  agent_name: string; template_yaml: string; version?: string; parameters?: any; created_by?: string;
}) => apiClient.post('/api/v1/ops/deployments', data);

export const getDeployment = (depId: string) =>
  apiClient.get(`/api/v1/ops/deployments/${depId}`);

export const updateDeploymentStatus = (depId: string, data: {
  status: string; error_message?: string; health_score?: number;
}) => apiClient.post(`/api/v1/ops/deployments/${depId}/status`, data);

export const rollbackDeployment = (depId: string) =>
  apiClient.post(`/api/v1/ops/deployments/${depId}/rollback`);

export const deleteDeployment = (depId: string) =>
  apiClient.delete(`/api/v1/ops/deployments/${depId}`);

export const getDeploymentStats = () =>
  apiClient.get('/api/v1/ops/deployments/stats');

// ==================== 4.22.2 Auto Scaling ====================
export const listScalingPolicies = (params?: { skip?: number; limit?: number; enabled_only?: boolean }) =>
  apiClient.get('/api/v1/ops/scaling/policies', { params });

export const upsertScalingPolicy = (data: any) =>
  apiClient.post('/api/v1/ops/scaling/policies', data);

export const getScalingPolicy = (policyId: string) =>
  apiClient.get(`/api/v1/ops/scaling/policies/${policyId}`);

export const evaluateScaling = (data: { agent_id: string; current_instances: number; metric_type: string; metric_value: number }) =>
  apiClient.post('/api/v1/ops/scaling/evaluate', data);

export const listScalingEvents = (params?: { agent_id?: string; days?: number; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/scaling/events', { params });

export const getScalingStats = (days?: number) =>
  apiClient.get('/api/v1/ops/scaling/stats', { params: { days } });

// ==================== 4.22.3 日志管理 ====================
export const ingestLog = (data: any) =>
  apiClient.post('/api/v1/ops/logs/ingest', data);

export const searchLogs = (params?: {
  level?: string; logger?: string; source_type?: string; agent_id?: string;
  keyword?: string; from_time?: string; to_time?: string; skip?: number; limit?: number;
}) => apiClient.get('/api/v1/ops/logs', { params });

export const getLogStats = (days?: number) =>
  apiClient.get('/api/v1/ops/logs/stats', { params: { days } });

export const listLogConfigs = (params?: { skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/logs/configs', { params });

export const upsertLogConfig = (data: any) =>
  apiClient.post('/api/v1/ops/logs/configs', data);

// ==================== 4.22.4 定期维护 ====================
export const listMaintenanceTasks = (params?: { task_type?: string; enabled_only?: boolean; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/maintenance/tasks', { params });

export const createMaintenanceTask = (data: any) =>
  apiClient.post('/api/v1/ops/maintenance/tasks', data);

export const getMaintenanceTask = (taskId: string) =>
  apiClient.get(`/api/v1/ops/maintenance/tasks/${taskId}`);

export const updateMaintenanceTask = (taskId: string, data: any) =>
  apiClient.put(`/api/v1/ops/maintenance/tasks/${taskId}`, data);

export const deleteMaintenanceTask = (taskId: string) =>
  apiClient.delete(`/api/v1/ops/maintenance/tasks/${taskId}`);

export const executeMaintenanceTask = (taskId: string, data: any) =>
  apiClient.post(`/api/v1/ops/maintenance/tasks/${taskId}/execute`, data);

export const listMaintenanceExecutions = (params?: { task_id?: string; days?: number; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/maintenance/executions', { params });

// ==================== 4.22.5 异常自愈 ====================
export const listHealRules = (params?: { agent_id?: string; enabled_only?: boolean; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/heal/rules', { params });

export const createHealRule = (data: any) =>
  apiClient.post('/api/v1/ops/heal/rules', data);

export const getHealRule = (ruleId: string) =>
  apiClient.get(`/api/v1/ops/heal/rules/${ruleId}`);

export const updateHealRule = (ruleId: string, data: any) =>
  apiClient.put(`/api/v1/ops/heal/rules/${ruleId}`, data);

export const deleteHealRule = (ruleId: string) =>
  apiClient.delete(`/api/v1/ops/heal/rules/${ruleId}`);

export const triggerHeal = (data: any) =>
  apiClient.post('/api/v1/ops/heal/trigger', data);

export const completeHeal = (recordId: string, data: any) =>
  apiClient.post(`/api/v1/ops/heal/${recordId}/complete`, data);

export const listHealRecords = (params?: { agent_id?: string; status?: string; days?: number; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/heal/records', { params });

export const getHealStats = (days?: number) =>
  apiClient.get('/api/v1/ops/heal/stats', { params: { days } });

// ==================== 4.22.6 运维报告 ====================
export const generateReport = (data: { report_type: string }) =>
  apiClient.post('/api/v1/ops/reports/generate', data);

export const listReports = (params?: { report_type?: string; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/ops/reports', { params });

export const getReport = (reportId: string) =>
  apiClient.get(`/api/v1/ops/reports/${reportId}`);

export const deleteReport = (reportId: string) =>
  apiClient.delete(`/api/v1/ops/reports/${reportId}`);

// ==================== 综合仪表盘 ====================
export const getOpsDashboard = () =>
  apiClient.get('/api/v1/ops/dashboard');

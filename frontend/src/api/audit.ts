import apiClient from './client';

// ==================== 审计日志 ====================
export const createAuditLog = (data: any) => apiClient.post('/api/v1/audit/logs', data);

export const listAuditLogs = (params?: any) => apiClient.get('/api/v1/audit/logs', { params });

export const getAuditLog = (logId: string) => apiClient.get(`/api/v1/audit/logs/${logId}`);

export const getAuditStats = () => apiClient.get('/api/v1/audit/stats');

// ==================== 防篡改校验 ====================
export const verifyAuditChain = () => apiClient.get('/api/v1/audit/verify');

export const verifyAuditRecord = (id: string) => apiClient.post('/api/v1/audit/verify', { id });

// ==================== 导出与 SIEM ====================
export const exportAuditCsv = (params?: any) =>
  apiClient.get('/api/v1/audit/export/csv', { params, responseType: 'blob' });

export const exportAuditSiem = (minutes = 60) =>
  apiClient.get('/api/v1/audit/siem/export', { params: { minutes }, responseType: 'text' });

// ==================== 异常行为检测 ====================
export const scanAnomalies = () => apiClient.post('/api/v1/audit/anomalies/scan');

export const listAnomalies = (params?: any) => apiClient.get('/api/v1/audit/anomalies', { params });

export const updateAnomalyStatus = (alertId: string, status: string) =>
  apiClient.patch(`/api/v1/audit/anomalies/${alertId}`, { status });

// ==================== 规则管理 ====================
export const listAuditRules = () => apiClient.get('/api/v1/audit/rules');

export const createAuditRule = (data: any) => apiClient.post('/api/v1/audit/rules', data);

export const updateAuditRule = (ruleId: string, data: any) =>
  apiClient.put(`/api/v1/audit/rules/${ruleId}`, data);

export const deleteAuditRule = (ruleId: string) =>
  apiClient.delete(`/api/v1/audit/rules/${ruleId}`);

// ==================== 归档与合规 ====================
export const listAuditArchives = () => apiClient.get('/api/v1/audit/archives');

export const runAuditArchive = () => apiClient.post('/api/v1/audit/archive');

export const runAuditRetention = () => apiClient.post('/api/v1/audit/retention');

// ==================== 审计配置 ====================
export const getAuditConfig = () => apiClient.get('/api/v1/audit/config');

export const updateAuditConfig = (data: any) => apiClient.put('/api/v1/audit/config', data);

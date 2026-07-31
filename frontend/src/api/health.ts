import apiClient from './client';

// ==================== 健康检查执行 ====================
export const runHealthCheck = (data: { agent_id: string; agent_name?: string; level?: string; metrics?: any }) =>
  apiClient.post('/api/v1/health/check', data);

export const listCheckRuns = (params?: { agent_id?: string; level?: string; limit?: number }) =>
  apiClient.get('/api/v1/health/check-runs', { params });

// ==================== 健康快照/面板 ====================
export const listSnapshots = (params?: { skip?: number; limit?: number; status?: string }) =>
  apiClient.get('/api/v1/health/snapshots', { params });

export const getSnapshot = (agentId: string) =>
  apiClient.get(`/api/v1/health/snapshots/${agentId}`);

export const getTop5Healthy = () =>
  apiClient.get('/api/v1/health/top5/healthy');

export const getTop5Unhealthy = () =>
  apiClient.get('/api/v1/health/top5/unhealthy');

export const getHealthTrend = (params?: { agent_id?: string; hours?: number }) =>
  apiClient.get('/api/v1/health/trend', { params });

export const getHealthOverview = () =>
  apiClient.get('/api/v1/health/overview');

export const listHealthEvents = (params?: { agent_id?: string; limit?: number }) =>
  apiClient.get('/api/v1/health/events', { params });

// ==================== 权重模板 ====================
export const listWeightTemplates = () =>
  apiClient.get('/api/v1/health/weights');

export const createWeightTemplate = (data: any) =>
  apiClient.post('/api/v1/health/weights', data);

export const deleteWeightTemplate = (templateId: string) =>
  apiClient.delete(`/api/v1/health/weights/${templateId}`);

// ==================== 检查配置 ====================
export const listHealthConfigs = (params?: { skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/health/configs', { params });

export const upsertHealthConfig = (data: any) =>
  apiClient.post('/api/v1/health/configs', data);

export const deleteHealthConfig = (agentId: string) =>
  apiClient.delete(`/api/v1/health/configs/${agentId}`);

// ==================== 雷达对比 ====================
export const compareAgentsHealth = (agentIds: string[]) =>
  apiClient.post('/api/v1/health/compare', { agent_ids: agentIds });

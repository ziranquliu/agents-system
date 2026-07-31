import apiClient from './client';

// ==================== 用量记录与统计 ====================
export const recordTokenUsage = (data: any) =>
  apiClient.post('/api/v1/tokens/usage/record', data);

export const getTokenStats = (params?: any) =>
  apiClient.get('/api/v1/tokens/stats', { params });

export const listTokenUsage = (params?: any) =>
  apiClient.get('/api/v1/tokens/usage', { params });

// ==================== 预算与配额 ====================
export const getTokenBudget = (userId: string) =>
  apiClient.get('/api/v1/tokens/budget', { params: { user_id: userId } });

export const updateTokenBudget = (data: any) =>
  apiClient.put('/api/v1/tokens/budget', data);

export const listTokenAlerts = (params?: any) =>
  apiClient.get('/api/v1/tokens/alerts', { params });

export const updateTokenAlert = (alertId: string, status: string) =>
  apiClient.patch(`/api/v1/tokens/alerts/${alertId}`, { status });

// ==================== 优化策略 ====================
export const optimizeContext = (data: any) =>
  apiClient.post('/api/v1/tokens/optimize/context', data);

export const suggestModel = (taskType: string, inputTokens = 0) =>
  apiClient.get('/api/v1/tokens/suggest', { params: { task_type: taskType, input_tokens: inputTokens } });

export const getCascadePlan = (taskType: string) =>
  apiClient.get('/api/v1/tokens/cascade', { params: { task_type: taskType } });

export const listCascadeRules = () => apiClient.get('/api/v1/tokens/cascade/rules');

export const saveCascadeRule = (data: any) => apiClient.post('/api/v1/tokens/cascade/rules', data);

export const getTokenEffectiveness = (days = 30) =>
  apiClient.get('/api/v1/tokens/effectiveness', { params: { days } });

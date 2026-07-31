import apiClient from './client';

export const getSchedulerStatus = () => apiClient.get('/api/v1/scheduler/status');

export const startScheduler = () => apiClient.post('/api/v1/scheduler/start');

export const stopScheduler = () => apiClient.post('/api/v1/scheduler/stop');

export const triggerSchedulerTask = (task: string) =>
  apiClient.post('/api/v1/scheduler/trigger', null, { params: { task } });

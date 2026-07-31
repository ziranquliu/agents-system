import apiClient from './client';

// ==================== 备份策略 ====================
export const listBackupPolicies = (params?: { skip?: number; limit?: number; enabled_only?: boolean }) =>
  apiClient.get('/api/v1/backup-enhanced/policies', { params });

export const upsertBackupPolicy = (data: any) =>
  apiClient.post('/api/v1/backup-enhanced/policies', data);

export const getBackupPolicyByAgent = (agentId: string) =>
  apiClient.get(`/api/v1/backup-enhanced/policies/agent/${agentId}`);

export const deleteBackupPolicy = (policyId: string) =>
  apiClient.delete(`/api/v1/backup-enhanced/policies/${policyId}`);

// ==================== 备份记录 ====================
export const createBackup = (data: { agent_id: string; agent_name?: string; backup_type?: string; scope?: string; encryption_enabled?: boolean }) =>
  apiClient.post('/api/v1/backup-enhanced/backups', data);

export const listBackups = (params?: { agent_id?: string; backup_type?: string; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/backup-enhanced/backups', { params });

export const getBackup = (backupId: string) =>
  apiClient.get(`/api/v1/backup-enhanced/backups/${backupId}`);

export const deleteBackup = (backupId: string) =>
  apiClient.delete(`/api/v1/backup-enhanced/backups/${backupId}`);

export const getBackupEnhancedStats = (days?: number) =>
  apiClient.get('/api/v1/backup-enhanced/stats', { params: { days } });

// ==================== 事件触发 ====================
export const triggerEventBackup = (data: { agent_id: string; event_type: string; event_meta?: any }) =>
  apiClient.post('/api/v1/backup-enhanced/events', data);

export const listBackupEvents = (params?: { agent_id?: string; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/backup-enhanced/events', { params });

// ==================== 恢复 ====================
export const createRestore = (data: { backup_id: string; restore_type?: string; target_agent_id: string; target_agent_name?: string }) =>
  apiClient.post('/api/v1/backup-enhanced/restores', data);

export const listRestores = (params?: { agent_id?: string; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/backup-enhanced/restores', { params });

export const getRestore = (restoreId: string) =>
  apiClient.get(`/api/v1/backup-enhanced/restores/${restoreId}`);

// ==================== 恢复演练 ====================
export const createDrill = (data: { agent_id: string; agent_name?: string; backup_id: string }) =>
  apiClient.post('/api/v1/backup-enhanced/drills', data);

export const completeDrill = (drillId: string, data: { restore_ok?: boolean; report_data?: any; error_message?: string }) =>
  apiClient.post(`/api/v1/backup-enhanced/drills/${drillId}/complete`, data);

export const listDrills = (params?: { agent_id?: string; skip?: number; limit?: number }) =>
  apiClient.get('/api/v1/backup-enhanced/drills', { params });

export const getDrillStats = (days?: number) =>
  apiClient.get('/api/v1/backup-enhanced/drills/stats', { params: { days } });

// ==================== 密钥管理 ====================
export const rotateKey = (note?: string) =>
  apiClient.post('/api/v1/backup-enhanced/keys/rotate', { note });

export const listKeys = () =>
  apiClient.get('/api/v1/backup-enhanced/keys');

// ==================== 概览 ====================
export const getBackupEnhancedDashboard = () =>
  apiClient.get('/api/v1/backup-enhanced/dashboard');

/**
 * 审计日志页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button, Select } from 'antd';
import { ReloadOutlined, ExportOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface AuditLog {
  id: string;
  action: string;
  user_id: string;
  resource_type: string;
  resource_id: string;
  ip_address: string;
  timestamp: string;
  success: boolean;
}

const AuditPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<AuditLog[]>('/audit');
      setLogs(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
    { title: '操作', dataIndex: 'action', key: 'action', render: (v: string) => <Tag>{v}</Tag> },
    { title: '用户', dataIndex: 'user_id', key: 'user_id' },
    { title: '资源', dataIndex: 'resource_type', key: 'resource_type', render: (v: string, r: AuditLog) => `${v}:${r.resource_id}` },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip_address' },
    { title: '结果', dataIndex: 'success', key: 'success', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '成功' : '失败'}</Tag> },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>审计日志</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button icon={<ExportOutlined />}>导出 PDF</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={logs} rowKey="id" loading={loading} pagination={{ pageSize: 50 }} />
      </Card>
    </div>
  );
};

export default AuditPage;

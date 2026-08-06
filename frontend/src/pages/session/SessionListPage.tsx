/**
 * 会话管理页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Session {
  id: string;
  agent_id: string;
  user_id: string;
  status: string;
  message_count: number;
  created_at: string;
}

const statusColors: Record<string, string> = { active: 'green', idle: 'blue', archived: 'default', error: 'red' };

const SessionListPage: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<Session[]>('/sessions');
      setSessions(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const columns = [
    { title: '会话 ID', dataIndex: 'id', key: 'id', ellipsis: true },
    { title: 'Agent', dataIndex: 'agent_id', key: 'agent_id' },
    { title: '用户', dataIndex: 'user_id', key: 'user_id' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={statusColors[s] || 'default'}>{s}</Tag> },
    { title: '消息数', dataIndex: 'message_count', key: 'message_count' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>会话管理</Title>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>
      <Card>
        <Table columns={columns} dataSource={sessions} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
};

export default SessionListPage;

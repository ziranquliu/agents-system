/**
 * Agent 列表页
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Tag, Button, Space, Input, Card, Typography, Popconfirm, message } from 'antd';
import { PlusOutlined, SearchOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Agent {
  id: string;
  name: string;
  status: string;
  model_id: string;
  health_score: number;
  created_at: string;
}

const statusColors: Record<string, string> = {
  active: 'green', idle: 'blue', error: 'red', offline: 'default',
};

const AgentListPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  const loadAgents = async () => {
    setLoading(true);
    try {
      const res = await api.get<Agent[]>('/agents');
      setAgents(res.data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAgents(); }, []);

  const handleDelete = async (id: string) => {
    await api.delete(`/agents/${id}`);
    message.success('已删除');
    loadAgents();
  };

  const filtered = agents.filter(a => !search || a.name.toLowerCase().includes(search.toLowerCase()));

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (name: string, record: Agent) => <a onClick={() => navigate(`/agents/${record.id}`)}>{name}</a> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={statusColors[s] || 'default'}>{s}</Tag> },
    { title: '模型', dataIndex: 'model_id', key: 'model_id' },
    { title: '健康分', dataIndex: 'health_score', key: 'health_score', render: (v: number) => <span style={{ color: v > 80 ? '#52c41a' : v > 50 ? '#faad14' : '#ff4d4f' }}>{v}</span> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: Agent) => (
        <Space>
          <Button size="small" onClick={() => navigate(`/agents/${record.id}`)}>详情</Button>
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>Agent 管理</Title>
        <Space>
          <Input prefix={<SearchOutlined />} placeholder="搜索..." value={search} onChange={e => setSearch(e.target.value)} style={{ width: 200 }} />
          <Button icon={<ReloadOutlined />} onClick={loadAgents}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />}>新建 Agent</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={filtered} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
};

export default AgentListPage;

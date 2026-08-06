/**
 * 工作流页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button, Progress } from 'antd';
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Workflow {
  id: string;
  name: string;
  status: string;
  progress: number;
  node_count: number;
  created_at: string;
}

const statusColors: Record<string, string> = { running: 'blue', completed: 'green', failed: 'red', pending: 'default' };

const WorkflowPage: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<Workflow[]>('/workflows');
      setWorkflows(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={statusColors[s] || 'default'}>{s}</Tag> },
    { title: '进度', dataIndex: 'progress', key: 'progress', render: (v: number) => <Progress percent={v} size="small" /> },
    { title: '节点数', dataIndex: 'node_count', key: 'node_count' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>工作流管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />}>创建工作流</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={workflows} rowKey="id" loading={loading} />
      </Card>
    </div>
  );
};

export default WorkflowPage;

/**
 * MCP 管理页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button } from 'antd';
import { ReloadOutlined, AppstoreOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface MCP {
  name: string;
  status: string;
  tools_count: number;
  calls_total: number;
}

const MCPListPage: React.FC = () => {
  const [mcps, setMCPs] = useState<MCP[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<MCP[]>('/mcp/templates/installed');
      setMCPs(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'connected' ? 'green' : 'default'}>{v}</Tag> },
    { title: '工具数', dataIndex: 'tools_count', key: 'tools_count' },
    { title: '调用次数', dataIndex: 'calls_total', key: 'calls_total' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>MCP 管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<AppstoreOutlined />}>安装模板</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={mcps} rowKey="name" loading={loading} />
      </Card>
    </div>
  );
};

export default MCPListPage;

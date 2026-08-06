/**
 * 系统健康页
 */
import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Progress, Typography, Space, Table, Tag } from 'antd';
import { HeartOutlined, CheckCircleOutlined, WarningOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title, Text } = Typography;

interface HealthData {
  overall_score: number;
  components: { name: string; status: string; latency_ms: number; details: string }[];
}

const statusIcon: Record<string, React.ReactNode> = {
  healthy: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  degraded: <WarningOutlined style={{ color: '#faad14' }} />,
  unhealthy: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
};

const SystemHealthPage: React.FC = () => {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHealth();
    const timer = setInterval(loadHealth, 30000);
    return () => clearInterval(timer);
  }, []);

  const loadHealth = async () => {
    setLoading(true);
    try {
      const res = await api.get<HealthData>('/health/overview');
      setHealth(res.data);
    } finally { setLoading(false); }
  };

  const components = health?.components || [
    { name: 'PostgreSQL', status: 'healthy', latency_ms: 2, details: '连接正常' },
    { name: 'Redis', status: 'healthy', latency_ms: 1, details: '连接正常' },
    { name: 'Qdrant', status: 'degraded', latency_ms: 50, details: '内存模式' },
    { name: 'Elasticsearch', status: 'healthy', latency_ms: 10, details: '连接正常' },
  ];

  return (
    <div>
      <Title level={4}><HeartOutlined /> 系统健康</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card style={{ textAlign: 'center' }}>
            <Progress
              type="dashboard"
              percent={health?.overall_score || 85}
              size={200}
              strokeColor={health && health.overall_score > 80 ? '#52c41a' : '#faad14'}
            />
            <Title level={4} style={{ marginTop: 16 }}>综合健康评分</Title>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title="组件状态">
            <Table
              dataSource={components}
              rowKey="name"
              loading={loading}
              pagination={false}
              columns={[
                { title: '组件', dataIndex: 'name', key: 'name' },
                { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Space>{statusIcon[s]}<Tag color={s === 'healthy' ? 'green' : s === 'degraded' ? 'orange' : 'red'}>{s}</Tag></Space> },
                { title: '延迟', dataIndex: 'latency_ms', key: 'latency_ms', render: (v: number) => `${v}ms` },
                { title: '详情', dataIndex: 'details', key: 'details' },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default SystemHealthPage;

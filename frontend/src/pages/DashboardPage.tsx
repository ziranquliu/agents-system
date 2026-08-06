/**
 * 仪表盘首页 — 核心指标概览 + 趋势图
 */
import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Typography, Space, Spin } from 'antd';
import {
  RobotOutlined,
  MessageOutlined,
  DollarOutlined,
  HeartOutlined,
  RiseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '@/lib/api';

const { Title } = Typography;

interface OverviewData {
  agents: { total: number; active: number };
  sessions: { total: number; active: number };
  tokens: { used: number; cost_usd: number };
  health: { score: number; status: string };
}

const COLORS = ['#52c41a', '#1677ff', '#faad14', '#ff4d4f'];

const DashboardPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [metricsHistory, setMetricsHistory] = useState<{ time: string; requests: number; errors: number }[]>([]);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const [healthRes, metricsRes] = await Promise.all([
        api.get<OverviewData>('/health/overview').catch(() => ({ data: null })),
        api.get<{ time: string; requests: number; errors: number }[]>('/ws-monitor/metrics/history?duration_seconds=3600').catch(() => ({ data: [] })),
      ]);
      setOverview(healthRes.data);
      setMetricsHistory(metricsRes.data || []);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const pieData = overview ? [
    { name: '活跃', value: overview.agents?.active || 0 },
    { name: '空闲', value: (overview.agents?.total || 0) - (overview.agents?.active || 0) },
  ] : [];

  return (
    <div>
      <Title level={4}>系统概览</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="活跃 Agent"
              value={overview?.agents?.active || 0}
              suffix={`/ ${overview?.agents?.total || 0}`}
              prefix={<RobotOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="在线会话"
              value={overview?.sessions?.active || 0}
              suffix={`/ ${overview?.sessions?.total || 0}`}
              prefix={<MessageOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="今日成本"
              value={overview?.tokens?.cost_usd || 0}
              precision={4}
              prefix={<DollarOutlined style={{ color: '#faad14' }} />}
              suffix="USD"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="健康评分"
              value={overview?.health?.score || 0}
              prefix={<HeartOutlined style={{ color: '#ff4d4f' }} />}
              suffix="/ 100"
              valueStyle={{ color: (overview?.health?.score || 0) > 80 ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title={<Space><RiseOutlined /> 请求趋势</Space>}>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={metricsHistory}>
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="requests" stroke="#1677ff" fill="#1677ff" fillOpacity={0.2} name="请求" />
                <Area type="monotone" dataKey="errors" stroke="#ff4d4f" fill="#ff4d4f" fillOpacity={0.2} name="错误" />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title={<Space><ThunderboltOutlined /> Agent 状态</Space>}>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;

/**
 * 仪表盘配置页 — 拖拽布局
 */
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Typography, Row, Col, Button, Space, Empty, Tag, Spin } from 'antd';
import { PlusOutlined, SettingOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title, Text } = Typography;

interface Widget {
  id: string;
  widget_type: string;
  title: string;
  position: { x: number; y: number; w: number; h: number };
}

interface Dashboard {
  id: string;
  name: string;
  widgets: Widget[];
}

const widgetTypeLabels: Record<string, string> = {
  metric: '指标卡', chart: '图表', table: '表格', gauge: '仪表盘', log: '日志', alert_list: '告警列表', text: '文本', heatmap: '热力图',
};

const DashboardConfigPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) loadDashboard(id);
  }, [id]);

  const loadDashboard = async (dashId: string) => {
    setLoading(true);
    try {
      const res = await api.get<Dashboard>(`/dashboards/${dashId}`);
      setDashboard(res.data);
    } finally { setLoading(false); }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!dashboard) return <Empty description="仪表盘不存在" />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>{dashboard.name}</Title>
        <Space>
          <Button icon={<PlusOutlined />}>添加组件</Button>
          <Button icon={<SettingOutlined />}>配置</Button>
        </Space>
      </div>
      <Row gutter={[16, 16]}>
        {dashboard.widgets.length === 0 ? (
          <Col span={24}><Empty description="暂无组件, 点击添加" /></Col>
        ) : (
          dashboard.widgets.map(w => (
            <Col key={w.id} xs={24} sm={12} lg={Math.min(w.position.w * 2, 24)}>
              <Card title={<Space>{w.title}<Tag>{widgetTypeLabels[w.widget_type] || w.widget_type}</Tag></Space>} style={{ minHeight: 200 }}>
                <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Text type="secondary">组件数据加载中...</Text>
                </div>
              </Card>
            </Col>
          ))
        )}
      </Row>
    </div>
  );
};

export default DashboardConfigPage;

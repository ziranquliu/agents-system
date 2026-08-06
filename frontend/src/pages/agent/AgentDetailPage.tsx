/**
 * Agent 详情页 — 下钻分析 + 健康评分 + 瓶颈 + 建议
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Row, Col, Progress, List, Tag, Typography, Spin, Button, Space, Statistic } from 'antd';
import { ArrowLeftOutlined, AlertOutlined, BulbOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title, Text } = Typography;

interface DrilldownData {
  agent_id: string;
  metrics: {
    avg_response_time: number;
    p50_response_time: number;
    p95_response_time: number;
    p99_response_time: number;
    total_requests: number;
    successful_requests: number;
    failed_requests: number;
    error_rate: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_user_satisfaction: number;
  };
  bottlenecks: { dimension: string; metric: string; severity: string; description: string; suggestion: string }[];
  recommendations: { category: string; priority: string; title: string; description: string; expected_improvement: string }[];
  overall_health_score: number;
}

const AgentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DrilldownData | null>(null);

  useEffect(() => {
    if (id) loadDrilldown(id);
  }, [id]);

  const loadDrilldown = async (agentId: string) => {
    setLoading(true);
    try {
      const res = await api.get<DrilldownData>(`/agent-drilldown/${agentId}`);
      setData(res.data);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!data) return <Text>无数据</Text>;

  const severityColor: Record<string, string> = { critical: 'red', warning: 'orange' };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>Agent 下钻分析: {data.agent_id}</Title>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <Progress
                type="dashboard"
                percent={data.overall_health_score}
                strokeColor={data.overall_health_score > 80 ? '#52c41a' : data.overall_health_score > 50 ? '#faad14' : '#ff4d4f'}
              />
              <Title level={5} style={{ marginTop: 8 }}>综合健康评分</Title>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title="性能指标">
            <Descriptions column={3}>
              <Descriptions.Item label="平均响应">{data.metrics.avg_response_time.toFixed(2)}s</Descriptions.Item>
              <Descriptions.Item label="P95">{data.metrics.p95_response_time.toFixed(2)}s</Descriptions.Item>
              <Descriptions.Item label="P99">{data.metrics.p99_response_time.toFixed(2)}s</Descriptions.Item>
              <Descriptions.Item label="总请求数">{data.metrics.total_requests}</Descriptions.Item>
              <Descriptions.Item label="错误率">{(data.metrics.error_rate * 100).toFixed(1)}%</Descriptions.Item>
              <Descriptions.Item label="满意度">{data.metrics.avg_user_satisfaction.toFixed(1)}/5</Descriptions.Item>
              <Descriptions.Item label="总 Token">{data.metrics.total_tokens.toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="总成本">${data.metrics.total_cost_usd.toFixed(4)}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title={<Space><AlertOutlined /> 瓶颈检测</Space>}>
            {data.bottlenecks.length === 0 ? <Text type="secondary">暂无瓶颈</Text> : (
              <List
                dataSource={data.bottlenecks}
                renderItem={item => (
                  <List.Item>
                    <List.Item.Meta
                      title={<Space><Tag color={severityColor[item.severity]}>{item.severity}</Tag>{item.dimension}</Space>}
                      description={<>{item.description}<br /><Text type="secondary">建议: {item.suggestion}</Text></>}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={<Space><BulbOutlined /> 优化建议</Space>}>
            <List
              dataSource={data.recommendations}
              renderItem={item => (
                <List.Item>
                  <List.Item.Meta
                    title={<Space><Tag color={item.priority === 'high' ? 'red' : 'blue'}>{item.priority}</Tag>{item.title}</Space>}
                    description={<>{item.description}<br /><Text type="secondary">预期效果: {item.expected_improvement}</Text></>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default AgentDetailPage;

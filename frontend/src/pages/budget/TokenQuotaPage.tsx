/**
 * Token 配额管理页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button, Progress, Modal, Form, Input, InputNumber, Select, message } from 'antd';
import { PlusOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Quota {
  id: string;
  entity_type: string;
  entity_id: string;
  daily_limit: number;
  monthly_limit: number;
  daily_used: number;
  monthly_used: number;
  daily_remaining: number | null;
  monthly_remaining: number | null;
  alert_threshold: number;
}

const TokenQuotaPage: React.FC = () => {
  const [quotas, setQuotas] = useState<Quota[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [alerts, setAlerts] = useState<{ entity_id: string; alert_type: string; dimension: string; usage_percent: number }[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const [qRes, aRes] = await Promise.all([
        api.get<Quota[]>('/quotas'),
        api.get<{ entity_id: string; alert_type: string; dimension: string; usage_percent: number }[]>('/quotas/alerts'),
      ]);
      setQuotas(qRes.data || []);
      setAlerts(aRes.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (values: Record<string, unknown>) => {
    await api.post('/quotas', values);
    message.success('配额创建成功');
    setModalOpen(false);
    form.resetFields();
    load();
  };

  const columns = [
    { title: '实体类型', dataIndex: 'entity_type', key: 'entity_type', render: (v: string) => <Tag color={v === 'user' ? 'blue' : v === 'agent' ? 'green' : 'purple'}>{v}</Tag> },
    { title: '实体 ID', dataIndex: 'entity_id', key: 'entity_id' },
    {
      title: '日配额使用', key: 'daily',
      render: (_: unknown, r: Quota) => r.daily_limit > 0
        ? <Progress percent={Math.round(r.daily_used / r.daily_limit * 100)} size="small" status={r.daily_used >= r.daily_limit ? 'exception' : 'active'} />
        : <Tag>无限制</Tag>,
    },
    {
      title: '月配额使用', key: 'monthly',
      render: (_: unknown, r: Quota) => r.monthly_limit > 0
        ? <Progress percent={Math.round(r.monthly_used / r.monthly_limit * 100)} size="small" status={r.monthly_used >= r.monthly_limit ? 'exception' : 'active'} />
        : <Tag>无限制</Tag>,
    },
    { title: '告警阈值', dataIndex: 'alert_threshold', key: 'alert_threshold', render: (v: number) => `${(v * 100).toFixed(0)}%` },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>Token 配额管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>创建配额</Button>
        </Space>
      </div>

      {alerts.length > 0 && (
        <Card style={{ marginBottom: 16, borderColor: '#faad14' }}>
          <Space><WarningOutlined style={{ color: '#faad14' }} /><Title level={5} style={{ margin: 0 }}>配额告警</Title></Space>
          {alerts.map((a, i) => (
            <div key={i} style={{ marginTop: 4 }}>
              <Tag color="orange">{a.alert_type}</Tag> {a.entity_id} — {a.dimension}: {a.usage_percent}%
            </div>
          ))}
        </Card>
      )}

      <Card>
        <Table columns={columns} dataSource={quotas} rowKey="id" loading={loading} />
      </Card>

      <Modal title="创建配额" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="entity_type" label="实体类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'user', label: '用户' }, { value: 'agent', label: 'Agent' }, { value: 'project', label: '项目' }]} />
          </Form.Item>
          <Form.Item name="entity_id" label="实体 ID" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="daily_limit" label="日配额限制"><InputNumber style={{ width: '100%' }} min={0} placeholder="0 = 无限制" /></Form.Item>
          <Form.Item name="monthly_limit" label="月配额限制"><InputNumber style={{ width: '100%' }} min={0} placeholder="0 = 无限制" /></Form.Item>
          <Form.Item name="alert_threshold" label="告警阈值"><InputNumber style={{ width: '100%' }} min={0} max={1} step={0.1} defaultValue={0.8} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TokenQuotaPage;

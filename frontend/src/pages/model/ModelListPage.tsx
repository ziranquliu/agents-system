/**
 * 模型管理页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Card, Typography, Modal, Form, Input, InputNumber, message } from 'antd';
import { PlusOutlined, SwapOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Model {
  model_id: string;
  provider: string;
  is_active: boolean;
  is_current: boolean;
  priority: number;
}

const ModelListPage: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<Model[]>('/hotswap/models');
      setModels(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSwitch = async (modelId: string) => {
    await api.post('/hotswap/switch', { to_model: modelId, reason: '手动切换' });
    message.success(`已切换到 ${modelId}`);
    load();
  };

  const handleRegister = async (values: Record<string, unknown>) => {
    await api.post('/hotswap/models', values);
    message.success('注册成功');
    setModalOpen(false);
    form.resetFields();
    load();
  };

  const columns = [
    { title: '模型 ID', dataIndex: 'model_id', key: 'model_id' },
    { title: '供应商', dataIndex: 'provider', key: 'provider' },
    { title: '状态', dataIndex: 'is_active', key: 'is_active', render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '可用' : '禁用'}</Tag> },
    { title: '当前', dataIndex: 'is_current', key: 'is_current', render: (v: boolean) => v ? <Tag color="blue">当前使用</Tag> : null },
    { title: '优先级', dataIndex: 'priority', key: 'priority' },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: Model) => (
        <Space>
          {!record.is_current && <Button size="small" icon={<SwapOutlined />} onClick={() => handleSwitch(record.model_id)}>切换</Button>}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>模型管理</Title>
        <Space>
          <Button icon={<ThunderboltOutlined />} onClick={() => api.post('/hotswap/rollback').then(() => { message.success('已回滚'); load(); })}>回滚</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>注册模型</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={models} rowKey="model_id" loading={loading} />
      </Card>
      <Modal title="注册模型" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="model_id" label="模型 ID" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="provider" label="供应商" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="endpoint" label="端点"><Input /></Form.Item>
          <Form.Item name="max_tokens" label="最大 Token"><InputNumber style={{ width: '100%' }} defaultValue={4096} /></Form.Item>
          <Form.Item name="priority" label="优先级"><InputNumber style={{ width: '100%' }} defaultValue={0} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ModelListPage;

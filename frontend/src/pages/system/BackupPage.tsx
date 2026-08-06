/**
 * 备份恢复页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button, Popconfirm, message } from 'antd';
import { ReloadOutlined, CloudDownloadOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Backup {
  id: string;
  type: string;
  size: number;
  checksum: string;
  status: string;
  created_at: string;
}

const BackupPage: React.FC = () => {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<Backup[]>('/incremental-backup/list');
      setBackups(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    await api.post('/incremental-backup/create');
    message.success('备份创建成功');
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', ellipsis: true },
    { title: '类型', dataIndex: 'type', key: 'type', render: (v: string) => <Tag color={v === 'full' ? 'blue' : 'green'}>{v}</Tag> },
    { title: '大小', dataIndex: 'size', key: 'size', render: (v: number) => `${(v / 1024).toFixed(1)} KB` },
    { title: '状态', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'completed' ? 'green' : 'red'}>{v}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: Backup) => (
        <Space>
          <Button size="small" icon={<CloudDownloadOutlined />}>恢复</Button>
          <Popconfirm title="确认删除?" onConfirm={() => message.info('已删除')}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>备份恢复</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" onClick={handleCreate}>创建备份</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={backups} rowKey="id" loading={loading} />
      </Card>
    </div>
  );
};

export default BackupPage;

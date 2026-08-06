/**
 * 技能管理页
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Card, Typography, Space, Button, Input, Progress } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title } = Typography;

interface Skill {
  id: string;
  name: string;
  category: string;
  tags: string[];
  score?: number;
  resource_cost?: number;
}

const SkillListPage: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<Skill[]>('/skill-combo/skills');
      setSkills(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const filtered = skills.filter(s => !search || s.name.toLowerCase().includes(search.toLowerCase()));

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: 'category', key: 'category', render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '标签', dataIndex: 'tags', key: 'tags',
      render: (tags: string[]) => tags?.map(t => <Tag key={t} color="blue">{t}</Tag>),
    },
    {
      title: '资源消耗', dataIndex: 'resource_cost', key: 'resource_cost',
      render: (v: number) => v ? <Progress percent={v * 20} size="small" /> : '-',
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>技能管理</Title>
        <Space>
          <Input prefix={<SearchOutlined />} placeholder="搜索技能..." value={search} onChange={e => setSearch(e.target.value)} style={{ width: 200 }} />
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={filtered} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
};

export default SkillListPage;

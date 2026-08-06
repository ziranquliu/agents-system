/**
 * 知识库页
 */
import React, { useEffect, useState } from 'react';
import { Card, Typography, Space, Button, List, Input, Tag, Empty } from 'antd';
import { SearchOutlined, PlusOutlined, BookOutlined } from '@ant-design/icons';
import { api } from '@/lib/api';

const { Title, Text } = Typography;
const { Search } = Input;

interface KnowledgeItem {
  id: string;
  title: string;
  content: string;
  category: string;
  created_at: string;
}

const KnowledgePage: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<KnowledgeItem[]>('/knowledge');
      setItems(res.data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = async (value: string) => {
    if (!value) { load(); return; }
    setLoading(true);
    try {
      const res = await api.post<KnowledgeItem[]>('/knowledge/search', { query: value });
      setItems(res.data || []);
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>知识库</Title>
        <Space>
          <Search placeholder="语义搜索..." value={query} onChange={e => setQuery(e.target.value)} onSearch={handleSearch} style={{ width: 300 }} enterButton={<><SearchOutlined /> 搜索</>} />
          <Button type="primary" icon={<PlusOutlined />}>添加知识</Button>
        </Space>
      </div>
      <Card>
        {items.length === 0 ? <Empty description="暂无知识条目" /> : (
          <List
            loading={loading}
            dataSource={items}
            renderItem={item => (
              <List.Item>
                <List.Item.Meta
                  avatar={<BookOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                  title={<Space>{item.title}<Tag>{item.category}</Tag></Space>}
                  description={<Text type="secondary">{item.content?.substring(0, 200)}...</Text>}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
};

export default KnowledgePage;

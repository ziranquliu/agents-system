/**
 * 登录页
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, Space, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/lib/api';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string; user: { id: string; username: string; email: string; role: string } }>(
        '/auth/login',
        values,
      );
      if (res.code === 0 && res.data) {
        login(res.data.access_token, res.data.user);
        message.success('登录成功');
        navigate('/dashboard');
      } else {
        message.error(res.message || '登录失败');
      }
    } catch {
      message.error('登录失败, 请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f0f2f5' }}>
      <Card style={{ width: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}>
        <Space direction="vertical" style={{ width: '100%', textAlign: 'center', marginBottom: 24 }}>
          <Text style={{ fontSize: 48 }}>🤖</Text>
          <Title level={3} style={{ margin: 0 }}>智能体管理系统</Title>
          <Text type="secondary">Agent Management System</Text>
        </Space>
        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default LoginPage;

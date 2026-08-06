/**
 * 系统设置页
 */
import React, { useState } from 'react';
import { Card, Typography, Form, Input, Button, Switch, Divider, Space, Tabs, message } from 'antd';
import { SaveOutlined, KeyOutlined, BellOutlined, SafetyOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

const SettingsPage: React.FC = () => {
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 500));
    message.success('设置已保存');
    setSaving(false);
  };

  return (
    <div>
      <Title level={4}>系统设置</Title>
      <Tabs defaultActiveKey="general">
        <TabPane tab="基本设置" key="general">
          <Card>
            <Form layout="vertical" style={{ maxWidth: 600 }}>
              <Form.Item label="系统名称"><Input defaultValue="智能体管理系统" /></Form.Item>
              <Form.Item label="管理员邮箱"><Input defaultValue="admin@example.com" /></Form.Item>
              <Form.Item label="API 限流 (请求/分钟)"><Input type="number" defaultValue="600" /></Form.Item>
              <Form.Item label="启用 HTTPS"><Switch defaultChecked /></Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存设置</Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
        <TabPane tab="安全设置" key="security">
          <Card>
            <Form layout="vertical" style={{ maxWidth: 600 }}>
              <Form.Item label="JWT 过期时间 (小时)"><Input type="number" defaultValue="24" /></Form.Item>
              <Form.Item label="密码最小长度"><Input type="number" defaultValue="8" /></Form.Item>
              <Form.Item label="登录失败锁定次数"><Input type="number" defaultValue="5" /></Form.Item>
              <Form.Item label="启用双因素认证"><Switch /></Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SafetyOutlined />} onClick={handleSave}>保存安全设置</Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
        <TabPane tab="通知设置" key="notifications">
          <Card>
            <Form layout="vertical" style={{ maxWidth: 600 }}>
              <Form.Item label="邮件通知"><Switch defaultChecked /></Form.Item>
              <Form.Item label="SMTP 服务器"><Input defaultValue="smtp.example.com" /></Form.Item>
              <Form.Item label="飞书 Webhook"><Input placeholder="https://open.feishu.cn/..." /></Form.Item>
              <Form.Item label="钉钉 Webhook"><Input placeholder="https://oapi.dingtalk.com/..." /></Form.Item>
              <Form.Item>
                <Button type="primary" icon={<BellOutlined />} onClick={handleSave}>保存通知设置</Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default SettingsPage;

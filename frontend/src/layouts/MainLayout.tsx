/**
 * 主布局 — 侧边栏 + 顶栏 + 内容区
 */
import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Space, Typography, theme } from 'antd';
import {
  DashboardOutlined,
  RobotOutlined,
  ApiOutlined,
  ToolOutlined,
  DatabaseOutlined,
  MessageOutlined,
  BookOutlined,
  BranchesOutlined,
  CloudOutlined,
  SafetyOutlined,
  HeartOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  WalletOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/agents', icon: <RobotOutlined />, label: 'Agent 管理' },
  { key: '/models', icon: <ApiOutlined />, label: '模型管理' },
  { key: '/skills', icon: <ToolOutlined />, label: '技能管理' },
  { key: '/mcp', icon: <AppstoreOutlined />, label: 'MCP 管理' },
  { key: '/sessions', icon: <MessageOutlined />, label: '会话管理' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: '/workflows', icon: <BranchesOutlined />, label: '工作流' },
  { key: '/budget', icon: <WalletOutlined />, label: '预算/配额' },
  { key: '/backups', icon: <CloudOutlined />, label: '备份恢复' },
  { key: '/audit', icon: <SafetyOutlined />, label: '审计日志' },
  { key: '/health', icon: <HeartOutlined />, label: '系统健康' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { token: themeToken } = theme.useToken();

  const userMenuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人信息' },
    { key: 'settings', icon: <SettingOutlined />, label: '设置' },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
  ];

  const handleUserMenu = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
    }
  };

  const selectedKey = '/' + location.pathname.split('/')[1];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={sidebarCollapsed}
        onCollapse={toggleSidebar}
        theme="dark"
        width={220}
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Text strong style={{ color: '#fff', fontSize: sidebarCollapsed ? 14 : 18 }}>
            {sidebarCollapsed ? '🤖' : '🤖 智能体管理'}
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 24px', background: themeToken.colorBgContainer, display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
          <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenu }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} />
              <Text>{user?.username || '用户'}</Text>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: themeToken.colorBgContainer, borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;

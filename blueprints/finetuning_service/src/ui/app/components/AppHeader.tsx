'use client';

import { Layout, Typography, Button, Space } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined, SunOutlined, MoonOutlined, LoginOutlined } from '@ant-design/icons';
import { UserProfile, useNextAuth } from '@/src/features/auth';

const { Header } = Layout;
const { Title } = Typography;

interface AppHeaderProps {
  collapsed: boolean;
  onCollapse: () => void;
  theme: 'light' | 'dark';
  onThemeChange: () => void;
  onAuthClick?: () => void;
}

const AppHeader = ({ collapsed, onCollapse, theme, onThemeChange, onAuthClick }: AppHeaderProps) => {
  const { isAuthenticated, user } = useNextAuth();

  return (
    <Header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'fixed',
      width: '100%',
      zIndex: 1000,
      boxShadow: theme === 'dark' ? 'none' : '0px 1px 24.1px 0px #4953D526',
    }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={onCollapse}
          style={{
            fontSize: '16px',
            height: 64,
            marginRight: 16,
          }}
        />
        <Title level={3} style={{ color: theme === 'dark' ? 'white' : 'rgb(61, 68, 127)', margin: 0 }}>
          Intel AI for Enterprise Fine-Tuning
        </Title>
      </div>

      <Space size="middle">
        <Button
          type="text"
          icon={theme === 'dark' ? <SunOutlined /> : <MoonOutlined />}
          onClick={onThemeChange}
          style={{
            fontSize: '16px',
            width: 64,
            height: 64
          }}
        />

        {isAuthenticated && user ? (
          <UserProfile />
        ) : (
          <Button
            type="text"
            icon={<LoginOutlined />}
            onClick={onAuthClick}
            style={{
              fontSize: '16px',
              height: 64,
              paddingLeft: 16,
              paddingRight: 16,
            }}
          >
            Sign In
          </Button>
        )}
      </Space>
    </Header>
  );
};

export default AppHeader;
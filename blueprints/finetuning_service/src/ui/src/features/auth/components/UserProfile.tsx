import React from 'react';
import { Card, Avatar, Typography, Button, Dropdown, Space, Spin } from 'antd';
import { UserOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useNextAuth } from '../hooks';

const { Text, Title } = Typography;

export interface UserProfileProps {
  className?: string;
  showCard?: boolean;
}

export const UserProfile: React.FC<UserProfileProps> = ({
  className,
  showCard = false,
}) => {
  const { user, logout, isLoading } = useNextAuth();

  const handleLogout = () => {
    logout();
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: 'Profile Settings',
      icon: <SettingOutlined />,
      disabled: true,
      onClick: () => {
        // TODO: Implement profile settings
      },
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      label: 'Sign Out',
      icon: <LogoutOutlined />,
      onClick: handleLogout,
    },
  ];

  if (isLoading) {
    return (
      <div className={className}>
        <Spin size="small" />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const profileContent = (
    <Space align="center">
      <Avatar size="large" icon={<UserOutlined />} />
      <div>
        <Title level={5} style={{ margin: 0 }}>
          {user.name}
        </Title>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {user.email}
        </Text>
      </div>
    </Space>
  );

  const profileWithDropdown = (
    <Dropdown menu={{ items: menuItems }} placement="bottomRight" trigger={['click']}>
      <Button type="text" className="user-profile-button">
        {profileContent}
      </Button>
    </Dropdown>
  );

  if (showCard) {
    return (
      <Card className={className} style={{ textAlign: 'center' }}>
        <Space orientation="vertical" size="large">
          <Avatar size={64} icon={<UserOutlined />} />
          <div>
            <Title level={4} style={{ margin: 0 }}>
              {user.name}
            </Title>
            <Text type="secondary">{user.email}</Text>
          </div>
          <Button
            type="default"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            Sign Out
          </Button>
        </Space>
      </Card>
    );
  }

  return <div className={className}>{profileWithDropdown}</div>;
};

export const UserAvatar: React.FC<{ className?: string }> = ({ className }) => {
  const { user, isLoading } = useNextAuth();

  if (isLoading) {
    return <Spin size="small" className={className} />;
  }

  if (!user) {
    return <Avatar className={className} icon={<UserOutlined />} />;
  }

  return (
    <Avatar
      className={className}
      size="default"
      icon={<UserOutlined />}
      style={{ cursor: 'pointer' }}
    />
  );
};
'use client';

import React, { useState } from 'react';
import { Button, Card, Typography, Alert, Space } from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import { useNextAuth } from '../hooks';

const { Title, Text } = Typography;

export interface AuthFormsProps {
  onSuccess?: () => void;
  className?: string;
  onModeChange?: (mode: 'login' | 'register') => void;
}

export const LoginForm: React.FC<AuthFormsProps> = ({ className }) => {
  const { loginWithKeycloak, isLoading } = useNextAuth();
  const [error, setError] = useState<string | null>(null);

  const handleKeycloakLogin = async () => {
    try {
      setError(null);
      await loginWithKeycloak();
    } catch (err: any) {
      setError(err.message || 'Keycloak login failed. Please try again.');
    }
  };

  return (
    <Card className={className} style={{ maxWidth: 400, margin: '0 auto', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)' }}>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Title level={3}>Sign In</Title>
        <Text type="secondary">Sign in to your account</Text>
      </div>

      {error && (
        <Alert
          title="Login Failed"
          description={error}
          type="error"
          style={{ marginBottom: 16 }}
          showIcon
          closable
          onClose={() => setError(null)}
        />
      )}

      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Button
          type="default"
          size="large"
          block
          icon={<LoginOutlined />}
          onClick={handleKeycloakLogin}
          loading={isLoading}
        >
          Sign in with Keycloak
        </Button>
      </Space>
    </Card>
  );
};

export interface AuthModalProps {
  mode: 'login' | 'register';
  onModeChange: (mode: 'login' | 'register') => void;
  onSuccess?: () => void;
  className?: string;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  mode,
  onModeChange,
  onSuccess,
  className,
}) => {
  return (
    <div className={className}>
        <LoginForm onSuccess={onSuccess} onModeChange={onModeChange} />
    </div>
  );
};
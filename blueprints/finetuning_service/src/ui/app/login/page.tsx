'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Typography } from 'antd';
import { AuthModal, useNextAuth } from '@/src/features/auth';
import { useGlobalState } from '@core/state/globalState';

const { Title } = Typography;

export default function LoginPage() {
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const { isAuthenticated } = useNextAuth();
  const { state } = useGlobalState();
  const { theme: { mode: theme } } = state;
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router]);

  const handleAuthSuccess = () => {
    router.push('/');
  };

  const handleAuthModeChange = (mode: 'login' | 'register') => {
    setAuthMode(mode);
  };

  if (isAuthenticated) {
    return null; // Will redirect in useEffect
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      backgroundColor: theme === 'dark' ? '#090B1C' : '#F2F3FF',
    }}>
      <div style={{ width: '100%', maxWidth: '500px' }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <Title level={2} style={{
            color: theme === 'dark' ? '#c9d1d9' : '#3D447F',
            marginBottom: '8px'
          }}>
            Intel AI for Enterprise Finetuning
          </Title>
          <Typography.Text type="secondary">
            Sign in to access your fine-tuning workspace
          </Typography.Text>
        </div>
        <AuthModal
          mode={authMode}
          onModeChange={handleAuthModeChange}
          onSuccess={handleAuthSuccess}
        />
      </div>
    </div>
  );
}
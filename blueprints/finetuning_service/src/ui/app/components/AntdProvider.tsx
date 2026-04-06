'use client';

import React from 'react';
import { ConfigProvider, App } from 'antd';
import { createThemeConfig } from '@lib/antd-config';
import { initializeNotification } from '@notification';

interface AntdProviderProps {
  children: React.ReactNode;
  theme: 'light' | 'dark';
}

// Component to initialize the global notification API
const NotificationInitializer: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { notification } = App.useApp();

  React.useEffect(() => {
    initializeNotification(notification);
  }, [notification]);

  return <>{children}</>;
};

const AntdProvider = ({ children, theme }: AntdProviderProps) => {
  return (
    <ConfigProvider
      theme={createThemeConfig(theme)}
      // Use the newer button configuration format
      button={{ autoInsertSpace: false }}
    >
      <App>
        <NotificationInitializer>
          {children}
        </NotificationInitializer>
      </App>
    </ConfigProvider>
  );
};

export default AntdProvider;
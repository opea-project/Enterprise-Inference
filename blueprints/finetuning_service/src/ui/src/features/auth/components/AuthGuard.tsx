'use client';

import React from 'react';
import { Spin } from 'antd';
import { useNextAuth } from '../hooks';


export interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showModal?: boolean;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({
  children,
  fallback,
}) => {
  const { isAuthenticated, isLoading } = useNextAuth();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '200px'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return fallback || null;
  }

  return <>{children}</>;
};

export interface RequireAuthProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const RequireAuth: React.FC<RequireAuthProps> = ({ children, fallback }) => {
  return (
    <AuthGuard fallback={fallback} showModal={false}>
      {children}
    </AuthGuard>
  );
};
'use client';

import React from 'react';
import { Spin, Skeleton, Card, Space, Typography } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large';
  tip?: string;
  children?: React.ReactNode;
}

/**
 * Simple loading spinner component
 */
export function LoadingSpinner({ size = 'default', tip, children }: LoadingSpinnerProps) {
  const antIcon = <LoadingOutlined style={{ fontSize: size === 'large' ? 32 : size === 'small' ? 16 : 24 }} spin />;

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: children ? 'auto' : '200px',
      width: '100%'
    }}>
      <Spin
        indicator={antIcon}
        size={size}
        tip={tip}
        spinning={true}
      >
        {children}
      </Spin>
    </div>
  );
}

interface SkeletonLoadingProps {
  type?: 'list' | 'card' | 'table' | 'form' | 'detail';
  rows?: number;
  active?: boolean;
}

/**
 * Skeleton loading component for different content types
 */
export function SkeletonLoading({
  type = 'list',
  rows = 3,
  active = true
}: SkeletonLoadingProps) {
  switch (type) {
    case 'card':
      return (
        <Card style={{ margin: '16px 0' }}>
          <Skeleton active={active} avatar paragraph={{ rows: 2 }} />
        </Card>
      );

    case 'table':
      return (
        <div>
          {Array.from({ length: rows }, (_, index) => (
            <div key={index} style={{ marginBottom: 16 }}>
              <Skeleton active={active} paragraph={{ rows: 1 }} />
            </div>
          ))}
        </div>
      );

    case 'form':
      return (
        <Space orientation="vertical" style={{ width: '100%' }} size="large">
          {Array.from({ length: rows }, (_, index) => (
            <div key={index}>
              <Skeleton.Input active={active} style={{ width: 150, height: 20, marginBottom: 8 }} />
              <br />
              <Skeleton.Input active={active} style={{ width: '100%', height: 32 }} />
            </div>
          ))}
        </Space>
      );

    case 'detail':
      return (
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          <Skeleton.Input active={active} style={{ width: 300, height: 32 }} />
          <Skeleton active={active} paragraph={{ rows: 4 }} />
          <div style={{ marginTop: 20 }}>
            <Skeleton.Button active={active} style={{ marginRight: 10 }} />
            <Skeleton.Button active={active} />
          </div>
        </Space>
      );

    default: // list
      return (
        <div>
          {Array.from({ length: rows }, (_, index) => (
            <div key={index} style={{ marginBottom: 24 }}>
              <Skeleton active={active} avatar paragraph={{ rows: 2 }} />
            </div>
          ))}
        </div>
      );
  }
}

interface PageLoadingProps {
  title?: string;
  description?: string;
  type?: 'page' | 'section' | 'modal';
}

/**
 * Full page loading component
 */
export function PageLoading({
  title = 'Loading...',
  description,
  type = 'page'
}: PageLoadingProps) {
  const containerStyle = {
    page: {
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      padding: 40,
    },
    section: {
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      minHeight: '200px',
    },
    modal: {
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
      minHeight: '120px',
    },
  };

  return (
    <div style={containerStyle[type]}>
      <Spin
        size="large"
        indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
      />
      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Title level={4} style={{ margin: '8px 0' }}>
          {title}
        </Title>
        {description && (
          <Text type="secondary">{description}</Text>
        )}
      </div>
    </div>
  );
}

interface QueryLoadingProps {
  isLoading: boolean;
  isFetching?: boolean;
  loadingType?: 'spinner' | 'skeleton' | 'page';
  skeletonType?: 'list' | 'card' | 'table' | 'form' | 'detail';
  skeletonRows?: number;
  title?: string;
  description?: string;
  children: React.ReactNode;
}

/**
 * Wrapper component that handles loading states for queries
 */
export function QueryLoading({
  isLoading,
  isFetching = false,
  loadingType = 'skeleton',
  skeletonType = 'list',
  skeletonRows = 3,
  title,
  description,
  children
}: QueryLoadingProps) {
  // Show initial loading state
  if (isLoading) {
    switch (loadingType) {
      case 'spinner':
        return <LoadingSpinner tip="Loading..." />;
      case 'page':
        return <PageLoading title={title} description={description} />;
      default:
        return <SkeletonLoading type={skeletonType} rows={skeletonRows} />;
    }
  }

  // Show content with optional background loading indicator
  return (
    <Spin spinning={isFetching} tip="Updating...">
      {children}
    </Spin>
  );
}

export default QueryLoading;
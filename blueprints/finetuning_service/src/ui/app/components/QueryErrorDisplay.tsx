'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { Alert, Button, Space, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { AuthApiError } from '@/src/features/auth';
import { FilesApiServiceError } from '@features/files/api/client';
import { FineTuningApiError } from '@features/finetuning/api/client';
import { DataPrepApiServiceError } from '@features/dataprep/api/client';

const { Text } = Typography;

type QueryError = AuthApiError | FilesApiServiceError | FineTuningApiError | DataPrepApiServiceError | Error;

interface QueryErrorDisplayProps {
  error: QueryError | null;
  onRetry?: () => void;
  onDismiss?: () => void;
  showRetry?: boolean;
  showDismiss?: boolean;
  size?: 'small' | 'default' | 'large';
}

/**
 * Component to display query errors in a user-friendly way
 */
export function QueryErrorDisplay({
  error,
  onRetry,
  onDismiss,
  showRetry = true,
  showDismiss = false,
  size = 'default'
}: QueryErrorDisplayProps) {
  if (!error) return null;

  const getErrorMessage = (err: QueryError): string => {
    if ('message' in err && err.message) {
      return err.message;
    }
    return 'An unexpected error occurred';
  };

  const getErrorType = (err: QueryError): 'error' | 'warning' | 'info' => {
    if ('code' in err) {
      switch (err.code) {
        case 'NETWORK_ERROR':
        case 'TIMEOUT':
          return 'warning';
        case 'UNAUTHORIZED':
        case 'FORBIDDEN':
          return 'error';
        default:
          return 'error';
      }
    }
    return 'error';
  };

  const getErrorDescription = (err: QueryError): string => {
    if ('code' in err) {
      switch (err.code) {
        case 'NETWORK_ERROR':
          return 'Please check your internet connection and try again.';
        case 'TIMEOUT':
          return 'The request took too long to complete. Please try again.';
        case 'UNAUTHORIZED':
          return 'You need to log in to access this resource.';
        case 'FORBIDDEN':
          return 'You don\'t have permission to access this resource.';
        case 'HTTP_ERROR':
          return 'There was a problem with the server. Please try again later.';
        default:
          return 'Please try again or contact support if the problem persists.';
      }
    }
    return 'Please try again or contact support if the problem persists.';
  };

  const errorType = getErrorType(error);
  const errorMessage = getErrorMessage(error);
  const errorDescription = getErrorDescription(error);

  const actions = [];

  if (showRetry && onRetry) {
    actions.push(
      <Button
        key="retry"
        size={size === 'large' ? 'middle' : 'small'}
        icon={<ReloadOutlined />}
        onClick={onRetry}
      >
        Retry
      </Button>
    );
  }

  if (showDismiss && onDismiss) {
    actions.push(
      <Button
        key="dismiss"
        size={size === 'large' ? 'middle' : 'small'}
        type="text"
        onClick={onDismiss}
      >
        Dismiss
      </Button>
    );
  }

  return (
    <Alert
      type={errorType}
      title={errorMessage}
      description={
        <Space orientation="vertical" size="small" style={{ width: '100%' }}>
          <Text type="secondary">{errorDescription}</Text>
          {process.env.NODE_ENV === 'development' && 'code' in error && (
            <Text code style={{ fontSize: '12px' }}>
              Error Code: {error.code}
            </Text>
          )}
        </Space>
      }
      action={
        actions.length > 0 ? (
          <Space size="small">
            {actions}
          </Space>
        ) : undefined
      }
      showIcon
      style={{ marginBottom: 16 }}
    />
  );
}

interface QueryErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: QueryError, retry: () => void) => ReactNode;
}

/**
 * Error boundary specifically for query errors
 */
export function QueryErrorBoundary({ children, fallback }: QueryErrorBoundaryProps) {
  const [error, setError] = useState<QueryError | null>(null);

  const retry = () => {
    setError(null);
  };

  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      setError(new Error(event.message));
    };

    const handleRejection = (event: PromiseRejectionEvent) => {
      setError(event.reason);
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleRejection);
    };
  }, []);

  if (error) {
    if (fallback) {
      return <>{fallback(error, retry)}</>;
    }

    return (
      <div style={{ padding: 20 }}>
        <QueryErrorDisplay
          error={error}
          onRetry={retry}
          showRetry={true}
          size="large"
        />
      </div>
    );
  }

  return <>{children}</>;
}

export default QueryErrorDisplay;
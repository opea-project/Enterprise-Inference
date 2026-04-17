'use client';

import React from 'react';
import { Card, Typography, Table, Button, Space, Tag, Progress, App, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StopOutlined, EyeOutlined, ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { useFineTuningJobsList, useCancelFineTuningJob } from '@features/finetuning/hooks';
import { QueryLoading, QueryErrorDisplay } from '@/app/components';
import { FineTuningJob, FineTuningJobStatus } from '@features/finetuning/types';
import {
  transformFineTuningJobForDisplay,
  getFineTuningStatusColor,
  formatHyperparameters,
  formatCreatedAt,
  formatJobDuration,
  canCancelFineTuningJob
} from '@features/finetuning/utils';
import { FileNameDisplay } from '../files/components';

const { Title, Text } = Typography;

const FineTuningPageContent = () => {
  const router = useRouter();
  const { modal } = App.useApp();

  // Use TanStack Query hooks
  const {
    data: jobsResponse,
    isLoading,
    isError,
    error,
    refetch,
    isFetching
  } = useFineTuningJobsList({ limit: 100 });

  const cancelJobMutation = useCancelFineTuningJob();

  const jobsData = jobsResponse?.data || [];

  const handleCancelJob = async (jobId: string) => {
    modal.confirm({
      title: 'Cancel Fine-Tuning Job',
      content: 'Are you sure you want to cancel this fine-tuning job?',
      okText: 'Yes, Cancel',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await cancelJobMutation.mutateAsync(jobId);
        } catch {
          // Error handled by mutation
        }
      },
    });
  };

  const handleRefresh = () => {
    refetch();
  };

  const handleViewJob = (jobId: string) => {
    router.push(`/finetuning/${jobId}`);
  };

  const columns: ColumnsType<FineTuningJob> = [
    {
      title: 'Job ID',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      render: (jobId: string) => (
        <Button
          type="link"
          style={{ padding: 0, fontSize: '12px' }}
          onClick={() => handleViewJob(jobId)}
        >
          <Text code style={{ fontSize: '12px' }}>
            {jobId.substring(0, 12)}...
          </Text>
        </Button>
      ),
    },
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
      width: 150,
      ellipsis: true,
      render: (modelName: string) => (
        <Tooltip title={modelName}>
          <Text>{modelName.split('/').pop() || modelName}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: FineTuningJobStatus) => (
        <Tag color={getFineTuningStatusColor(status)}>
          {status.replace('_', ' ').toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 150,
      render: (_value: unknown, record) => {
        const transformed = transformFineTuningJobForDisplay(record);
        return record.status === 'queued' ? (
          <Text type="secondary">Queued</Text>
        ) : (
          <Progress
            percent={transformed.displayProgress}
            size="small"
            status={record.status === 'failed' ? 'exception' : undefined}
            showInfo={transformed.displayProgress > 0}
          />
        );
      },
    },
    {
      title: 'Training File',
      dataIndex: 'training_file',
      key: 'training_file',
      width: 150,
      ellipsis: true,
      render: (trainingFile: string) => (
        <FileNameDisplay fileId={trainingFile} />
      ),
    },
    {
      title: 'Hyperparameters',
      key: 'hyperparameters',
      width: 180,
      render: (_value: unknown, record) => (
        <Text style={{ fontSize: '12px' }}>
          {formatHyperparameters(record.hyperparameters)}
        </Text>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (createdAt: number) => (
        <Text style={{ fontSize: '12px' }}>
          {formatCreatedAt(createdAt)}
        </Text>
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 100,
      hidden: true,
      render: (_value: unknown, record) => (
        <Text style={{ fontSize: '12px' }}>
          {formatJobDuration(record)}
        </Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_value: unknown, record) => (
        <Space size="small">
          {canCancelFineTuningJob(record) && (
            <Button
              type="text"
              icon={<StopOutlined />}
              size="small"
              danger
              title="Cancel Job"
              onClick={() => handleCancelJob(record.id)}
            />
          )}
          <Button
            type="text"
            icon={<EyeOutlined />}
            size="small"
            title="View Details"
            onClick={() => handleViewJob(record.id)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>
        Fine-Tuning Jobs
      </Title>

      {/* Error Display */}
      {isError && (
        <QueryErrorDisplay
          error={error}
          onRetry={handleRefresh}
          showRetry={true}
        />
      )}

      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => router.push('/finetuning/new')}
            >
              Create Fine-Tuning Job
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={isFetching}
            >
              Refresh
            </Button>
          </Space>
        </div>

        <QueryLoading
          isLoading={isLoading}
          isFetching={isFetching}
          loadingType="skeleton"
          skeletonType="table"
          skeletonRows={5}
        >
          <Table
            columns={columns}
            dataSource={jobsData.map((job: FineTuningJob) => ({ ...job, key: job.id }))}
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) =>
                `${range[0]}-${range[1]} of ${total} fine-tuning jobs`,
            }}
            scroll={{ x: 1400 }}
          />
        </QueryLoading>
      </Card>
    </div>
  );
};

const FineTuningPage = () => {
  return <FineTuningPageContent />;
};

export default FineTuningPage;
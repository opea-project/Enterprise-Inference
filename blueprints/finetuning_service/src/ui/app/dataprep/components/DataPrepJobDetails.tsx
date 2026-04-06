'use client';

import React from 'react';
import {
  Card,
  Descriptions,
  Tag,
  Typography,
  Space,
  Button,
  Alert,
  Progress,
  Timeline,
  Popover,
} from 'antd';
import {
  InfoCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useJobStatus, useDataPrepUtilities } from '@features/dataprep/hooks';
import { QueryLoading, QueryErrorDisplay } from '@/app/components';
import type { JobWithStatus } from '@features/dataprep/types';
import { DataPrepStatus } from '@features/dataprep/types';
import { FileNameDisplay } from '@/app/files/components';

const { Title, Text } = Typography;

interface DataPrepJobDetailsProps {
  job: JobWithStatus;
  onRefresh?: () => void;
}

const DataPrepJobDetails: React.FC<DataPrepJobDetailsProps> = ({
  job,
  onRefresh
}) => {
  // Get real-time job status
  const {
    data: currentStatus,
    isLoading,
    isError,
    error,
    refetch,
  } = useJobStatus(job.job_id);

  const {
    isJobActive,
    isJobComplete,
    getJobStatusColor,
  } = useDataPrepUtilities();

  // Merge current status with job data (currentStatus has limited fields)
  const jobData = currentStatus ? {
    ...job,
    status: currentStatus.status,
    result: currentStatus.result,
    error: currentStatus.error,
  } : job;
  const isActive = isJobActive(jobData.status);
  const isComplete = isJobComplete(jobData.status);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case DataPrepStatus.SUCCESS:
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case DataPrepStatus.FAILURE:
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case DataPrepStatus.PROCESSING:
        return <SyncOutlined spin style={{ color: '#1890ff' }} />;
      default:
        return <InfoCircleOutlined />;
    }
  };

  const getProgressPercent = (status: string) => {
    switch (status) {
      case DataPrepStatus.SUCCESS:
        return 100;
      case DataPrepStatus.FAILURE:
        return 100;
      case DataPrepStatus.PROCESSING:
        return 60; // Show active progress
      default:
        return 0;
    }
  };

  const getProgressStatus = (status: string): "success" | "exception" | "active" | "normal" => {
    switch (status) {
      case DataPrepStatus.SUCCESS:
        return 'success';
      case DataPrepStatus.FAILURE:
        return 'exception';
      case DataPrepStatus.PROCESSING:
        return 'active';
      default:
        return 'normal';
    }
  };

  return (
    <Card
      title={
        <Space>
          <Title level={4} style={{ margin: 0 }}>
            Job Details
          </Title>
          <Tag color={getJobStatusColor(jobData.status)}>
            {jobData.status.toUpperCase()}
          </Tag>
        </Space>
      }
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={() => {
            refetch();
            onRefresh?.();
          }}
          loading={isLoading}
          size="small"
        >
          Refresh
        </Button>
      }
    >
      {/* Error Display */}
      {isError && (
        <div style={{ marginBottom: 16 }}>
          <QueryErrorDisplay
            error={error}
            onRetry={() => refetch()}
            showRetry={true}
          />
        </div>
      )}

      <QueryLoading isLoading={isLoading} loadingType="skeleton">
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          {/* Status Alert */}
          {isActive && (
            <Alert
              title="Job is Processing"
              description="This job is currently being processed. The status will update automatically."
              type="info"
              showIcon
              icon={<SyncOutlined spin />}
            />
          )}

          {isComplete && jobData.status === DataPrepStatus.SUCCESS && (
            <Alert
              title="Job Completed Successfully"
              description="The data preparation job has been completed successfully."
              type="success"
              showIcon
            />
          )}

          {isComplete && jobData.status === DataPrepStatus.FAILURE && (
            <Alert
              title="Job Failed"
              description={jobData.error || "The data preparation job encountered an error."}
              type="error"
              showIcon
            />
          )}

          {/* Progress */}
          <Card size="small" title="Progress">
            <Progress
              percent={getProgressPercent(jobData?.status || '')}
              status={getProgressStatus(jobData?.status || '')}
            />
            <div style={{ marginTop: 8 }}>
              <Space>
                {getStatusIcon(jobData.status)}
                <Text>{jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1)}</Text>
              </Space>
            </div>
          </Card>

          {/* Basic Information */}
          <Descriptions title="Job Information" bordered column={2} size="small">
            <Descriptions.Item label="Job ID">
              <Typography.Text code copyable>
                {jobData.job_id}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Submitted At">
              {new Date(jobData.submitted_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="File ID">
              {jobData.file_id.includes(',') ? (
                (() => {
                  const fileIds = jobData.file_id.split(',').map((id: string) => id.trim());
                  const count = fileIds.length;
                  const content = (
                    <Space orientation="vertical" size="small" style={{ maxWidth: 400 }}>
                      {fileIds.map((fileId: string) => (
                        <FileNameDisplay
                          key={fileId}
                          fileId={fileId}
                          showDownload={true}
                        />
                      ))}
                    </Space>
                  );
                  return (
                    <Popover content={content} title={`${count} Input Files`} trigger="hover">
                      <Space size={4}>
                        <FileNameDisplay
                          fileId={fileIds[0]}
                          showDownload={true}
                        />
                        <Tag color="blue" style={{ fontSize: '11px', padding: '0 4px', cursor: 'pointer' }}>
                          +{count - 1} more
                        </Tag>
                      </Space>
                    </Popover>
                  );
                })()
              ) : (
                <FileNameDisplay
                  fileId={jobData.file_id}
                  showDownload={true}
                />
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Space>
                {getStatusIcon(jobData.status)}
                <Tag color={getJobStatusColor(jobData.status)}>
                  {jobData.status.toUpperCase()}
                </Tag>
              </Space>
            </Descriptions.Item>
          </Descriptions>

          {/* Timing Statistics  */}
          {/* can be added here if the backend provides more detailed timing info (e.g. processing start/end time, time spent in queue, etc.) */}
          {/* <Row gutter={16}>0
            <Col span={12}>
              <Statistic
                title="Duration"
                value={formatJobDuration(jobData.submitted_at)}
                prefix={<ClockCircleOutlined />}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="Submitted"
                value={new Date(jobData.submitted_at).toLocaleTimeString()}
                prefix={<FileOutlined />}
              />
            </Col>
          </Row> */}

          {/* Results */}
          {jobData.result && (
            <Card size="small" title="Results">
              <Descriptions bordered column={2} size="small">
                <Descriptions.Item label="Output File">
                  <FileNameDisplay
                    fileId={jobData.result.aggregated_file_id}
                    showDownload={true}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="Total QA Pairs">
                  {jobData.result.total_qa_pairs}
                </Descriptions.Item>
                <Descriptions.Item label="Successful Files">
                  {jobData.result.successful_files}
                </Descriptions.Item>
                <Descriptions.Item label="Failed Files">
                  {jobData.result.failed_files}
                </Descriptions.Item>
                <Descriptions.Item label="Status">
                  <Tag color={jobData.result.status === 'completed' ? 'success' : 'default'}>
                    {jobData.result.status.toUpperCase()}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Message">
                  {jobData.result.message}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {/* Error Details */}
          {jobData.error && (
            <Card size="small" title="Error Details">
              <Alert
                title="Error Information"
                description={jobData.error}
                type="error"
                showIcon
              />
            </Card>
          )}


          {/* Timeline */}
          <Card size="small" title="Timeline">
            <Timeline>
              <Timeline.Item
                dot={<ClockCircleOutlined />}
                color="blue"
              >
                <strong>Job Submitted</strong>
                <br />
                <Text type="secondary">
                  {new Date(jobData.submitted_at).toLocaleString()}
                </Text>
              </Timeline.Item>

              {isActive && (
                <Timeline.Item
                  dot={<SyncOutlined spin />}
                  color="blue"
                >
                  <strong>Processing</strong>
                  <br />
                  <Text type="secondary">Job is currently being processed</Text>
                </Timeline.Item>
              )}

              {isComplete && (
                <Timeline.Item
                  dot={jobData.status === DataPrepStatus.SUCCESS ?
                    <CheckCircleOutlined /> : <CloseCircleOutlined />}
                  color={jobData.status === DataPrepStatus.SUCCESS ? 'green' : 'red'}
                >
                  <strong>
                    {jobData.status === DataPrepStatus.SUCCESS ? 'Completed' : 'Failed'}
                  </strong>
                  <br />
                  <Text type="secondary">
                    Job {jobData.status === DataPrepStatus.SUCCESS ? 'success' : jobData.status}
                    {jobData.error && ` with error: ${jobData.error}`}
                  </Text>
                </Timeline.Item>
              )}
            </Timeline>
          </Card>
        </Space>
      </QueryLoading>
    </Card>
  );
};

export default DataPrepJobDetails;
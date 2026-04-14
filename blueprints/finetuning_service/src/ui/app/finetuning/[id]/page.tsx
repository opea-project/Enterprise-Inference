'use client';

import React, { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Tag,
  Progress,
  Alert,
  Spin,
  App,
  Descriptions,
  Timeline,
  Row,
  Col,
  Statistic,
  Input,
} from 'antd';
import {
  ArrowLeftOutlined,
  StopOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { useRouter, useParams } from 'next/navigation';
import { useFineTuningJob, useJobEvents, useCancelFineTuningJob } from '@features/finetuning';
import { FileNameDisplay } from '@/app/files/components';
import {
  getFineTuningStatusColor,
  formatCreatedAt,
  formatJobDuration,
  canCancelFineTuningJob,
  getFineTuningStatusText,
  getFineTuningProgress,
} from '@features/finetuning/utils';

const { Title, Text } = Typography;

const FineTuningJobDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const { modal } = App.useApp();
  const [isCopied, setIsCopied] = useState(false);

  const jobId = params.id as string;

  const {
    data: jobData,
    isLoading: loading,
    error,
    refetch: refetchJob
  } = useFineTuningJob(jobId);

  const {
    data: jobEventsData,
    isLoading: eventsLoading,
    refetch: refetchEvents
  } = useJobEvents(jobId, { limit: 100 });

  const cancelJobMutation = useCancelFineTuningJob({
    onSuccess: () => {
      refetchJob();
    },
  });

  // Get the result file ID
  const resultFileId = jobData?.result_files?.[0];

  const jobEvents = jobEventsData?.data || [];

  const handleCancelJob = async () => {
    if (!jobData) return;

    modal.confirm({
      title: 'Cancel Fine-Tuning Job',
      content: 'Are you sure you want to cancel this fine-tuning job? This action cannot be undone.',
      okText: 'Yes, Cancel',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          cancelJobMutation.mutate(jobData.id);
        } catch {
          // Error handled by mutation
        }
      },
    });
  };

  const handleRefresh = () => {
    refetchJob();
    refetchEvents();
  };

  const handleBack = () => {
    router.push('/finetuning');
  };

  const getEventIcon = (level: string) => {
    switch (level) {
      case 'info': return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
      case 'warn': return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
      case 'error': return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default: return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    }
  };

  const renderJobStatus = () => {
    if (!jobData) return null;

    const progress = getFineTuningProgress(jobData.status);
    const statusText = getFineTuningStatusText(jobData.status);
    const statusColor = getFineTuningStatusColor(jobData.status);

    return (
      <Card title="Job Status" size="small">
        <Space orientation="vertical" style={{ width: '100%' }}>
          <div>
            <Tag color={statusColor} style={{ fontSize: '14px', padding: '4px 8px' }}>
              {statusText}
            </Tag>
          </div>
          <Progress
            percent={progress}
            status={jobData.status === 'failed' ? 'exception' : undefined}
            showInfo
          />
          {jobData.error && (
            <Alert
              title="Job Error"
              description={`${jobData.error.code}: ${jobData.error.message}`}
              type="error"
              showIcon
            />
          )}
        </Space>
      </Card>
    );
  };

  const renderJobMetrics = () => {
    if (!jobData) return null;

    return (
      <Card title="Job Metrics" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="Trained Tokens"
              value={jobData.trained_tokens || 0}
              formatter={(value) => value?.toLocaleString() || '0'}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Duration"
              value={formatJobDuration(jobData)}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Result Files"
              value={jobData.result_files?.length || 0}
            />
          </Col>
        </Row>
      </Card>
    );
  };

  const renderDeploymentStatus = () => {
    if (!jobData || jobData.status !== 'succeeded' || !resultFileId) return null;

    const helmCommand = `helm install test-finetuned-model vllm/ \\
  -f vllm/xeon-values.yaml \\
  --set finetune.enabled=true \\
  --set finetune.fileId=${resultFileId} \\
  --set LLM_MODEL_ID=/models/model \\
  --set pvc.enabled=false \\
  --set tensor_parallel_size=1 \\
  --set pipeline_parallel_size=1`;

    return (
      <Card title="Deployment Command" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            message="Deploy with Helm"
            description="Use the following Helm command to deploy your fine-tuned model."
            type="info"
            showIcon
          />

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong>Helm Install Command:</Text>
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={async () => {
                  await navigator.clipboard.writeText(helmCommand);
                  setIsCopied(true);
                  setTimeout(() => setIsCopied(false), 2000);
                }}
              >
                {isCopied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <Input.TextArea
              value={helmCommand}
              readOnly
              autoSize={{ minRows: 8, maxRows: 12 }}
              style={{
                fontFamily: 'monospace',
                fontSize: '13px',
                backgroundColor: '#f5f5f5'
              }}
            />
          </div>

          <Alert
            message="Model File ID"
            description={
              <Space direction="vertical" size="small">
                <Text>The command above uses your model file ID: <Text code copyable>{resultFileId}</Text></Text>
                <Text type="secondary">Customize the release name and other parameters as needed.</Text>
              </Space>
            }
            type="success"
            showIcon
          />
        </Space>
      </Card>
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>Loading fine-tuning job details...</Text>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          style={{ marginBottom: 16 }}
        >
          Back to Fine-Tuning Jobs
        </Button>
        <Alert
          title="Error Loading Job Details"
          description={error?.message || 'Failed to load job details'}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={handleRefresh}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  if (!jobData) {
    return (
      <div>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          style={{ marginBottom: 16 }}
        >
          Back to Fine-Tuning Jobs
        </Button>
        <Alert
          title="Job Not Found"
          description="The requested fine-tuning job could not be found."
          type="warning"
          showIcon
        />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          style={{ marginBottom: 16 }}
        >
          Back to Fine-Tuning Jobs
        </Button>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={2} style={{ marginBottom: 8 }}>
              Fine-Tuning Job Details
            </Title>
            <Text code style={{ fontSize: '16px' }}>{jobData.id}</Text>
          </div>

          <Space>
            {canCancelFineTuningJob(jobData) && (
              <Button
                icon={<StopOutlined />}
                danger
                onClick={handleCancelJob}
              >
                Cancel Job
              </Button>
            )}
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
            >
              Refresh
            </Button>
          </Space>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          {renderJobStatus()}
        </Col>
        <Col xs={24} lg={12}>
          {renderJobMetrics()}
        </Col>
      </Row>

      {/* Deployment Status Card */}
      {jobData?.status === 'succeeded' && resultFileId && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24}>
            {renderDeploymentStatus()}
          </Col>
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title={<><RobotOutlined /> Model Information</>} size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Base Model">
                <Text strong>{jobData.model}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Fine-Tuned Model">
                {jobData.fine_tuned_model ? (
                  <Text code>{jobData.fine_tuned_model}</Text>
                ) : (
                  <Text type="secondary">Not yet available</Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Organization">
                <Text>{jobData.organization_id}</Text>
              </Descriptions.Item>
              {jobData.suffix && (
                <Descriptions.Item label="Model Suffix">
                  <Text code>{jobData.suffix}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={<><FileTextOutlined /> Training Data</>} size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Training File">
                <FileNameDisplay fileId={jobData.training_file} />
              </Descriptions.Item>
              <Descriptions.Item label="Validation File">
                {jobData.validation_file ? (
                  <FileNameDisplay fileId={jobData.validation_file} />
                ) : (
                  <Text type="secondary">None specified</Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Result Files">
                {jobData.result_files && jobData.result_files.length > 0 ? (
                  <div>
                    {jobData.result_files.map((file, index) => (
                      <div key={index}>
                        <FileNameDisplay fileId={file} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary">No result files yet</Text>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title={<><SettingOutlined /> Hyperparameters</>} size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Epochs">
                {jobData.hyperparameters.n_epochs || 'Default (3)'}
              </Descriptions.Item>
              <Descriptions.Item label="Batch Size">
                {jobData.hyperparameters.batch_size || 'Default (4)'}
              </Descriptions.Item>
              <Descriptions.Item label="Learning Rate Multiplier">
                {jobData.hyperparameters.learning_rate_multiplier || 'Default (1.0)'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={<><ClockCircleOutlined /> Timeline</>} size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Created">
                {formatCreatedAt(jobData.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="Started">
                {jobData.created_at ? formatCreatedAt(jobData.created_at) : 'Not started'}
              </Descriptions.Item>
              <Descriptions.Item label="Finished">
                {jobData.finished_at ? formatCreatedAt(jobData.finished_at) : 'Not finished'}
              </Descriptions.Item>
              <Descriptions.Item label="Duration">
                {formatJobDuration(jobData)}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      {/* Job Events Timeline */}
      <Card
        title="Job Events"
        style={{ marginTop: 16 }}
        extra={
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => refetchEvents()}
            loading={eventsLoading}
          >
            Refresh Events
          </Button>
        }
      >
        {eventsLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary">Loading events...</Text>
            </div>
          </div>
        ) : jobEvents.length > 0 ? (
          <Timeline
            items={jobEvents.map((event, index) => {
              const eventDetails = event.data;
              const hasEventData = eventDetails !== null && eventDetails !== undefined;

              return {
                key: event.id || index,
                icon: getEventIcon(event.level),
                content: (
                  <div>
                    <Text strong style={{ color: event.level === 'error' ? '#ff4d4f' : undefined }}>
                      {event.message}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      {formatCreatedAt(event.created_at)} • Level: {event.level.toUpperCase()}
                    </Text>
                    {hasEventData && (
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {JSON.stringify(eventDetails, null, 2)}
                        </Text>
                      </div>
                    )}
                  </div>
                ),
              };
            })}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Text type="secondary">No events available for this job.</Text>
          </div>
        )}
      </Card>
    </div>
  );
};

export default FineTuningJobDetailPage;
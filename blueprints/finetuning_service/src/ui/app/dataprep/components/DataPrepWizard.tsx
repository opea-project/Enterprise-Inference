'use client';

import React, { useState } from 'react';
import {
  Card,
  Steps,
  Button,
  Space,
  Typography,
  Alert,
  List,
  Tag,
  Row,
  Col,
  Divider,
} from 'antd';
import {
  FileOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useFilesList } from '@features/files/hooks';
import { usePrepareDataMutation } from '@features/dataprep/hooks';
import { notify } from '@notification';
import { QueryErrorDisplay } from '@/app/components';
import FileExplorer from '@/app/files/components/FileExplorer';
import type { FileObject } from '@features/files/types';

const { Title, Text, Paragraph } = Typography;

interface DataPrepWizardProps {
  onJobsCreated?: (jobIds: string[]) => void;
}

const DataPrepWizard: React.FC<DataPrepWizardProps> = ({ onJobsCreated }) => {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [selectedFiles, setSelectedFiles] = useState<FileObject[]>([]);

  // Fetch files for selection
  const {
    data: filesResponse,
    isLoading: filesLoading,
    isError: filesError,
    error: filesErrorData,
    refetch: refetchFiles,
  } = useFilesList({ limit: 100, order: 'desc' });

  // Prepare data mutation
  const prepareDataMutation = usePrepareDataMutation({
    onSuccess: (response) => {
      notify.success({
        message: 'Data Preparation Started',
        description: `Successfully submitted ${response.submitted_job_ids.length} job(s) for processing.`,
      });
      setCurrentStep(2); // Move to completion step
      // Note: Cache invalidation is handled by the mutation hook and navigation is called after
      onJobsCreated?.(response.submitted_job_ids);
    },
    onError: (error) => {
      notify.error({
        message: 'Failed to Start Data Preparation',
        description: error.message,
      });
    },
  });

  const files = filesResponse?.data || [];

  const handleFileSelection = (selectedFiles: FileObject[]) => {
    setSelectedFiles(selectedFiles);
  };

  const handleSelectAll = () => {
    setSelectedFiles(files);
  };

  const handleClearSelection = () => {
    setSelectedFiles([]);
  };

  const handleNext = () => {
    if (currentStep === 0 && selectedFiles.length === 0) {
      notify.warning({
        message: 'No Files Selected',
        description: 'Please select at least one file to proceed.',
      });
      return;
    }
    setCurrentStep(prev => prev + 1);
  };

  const handlePrevious = () => {
    setCurrentStep(prev => prev - 1);
  };

  const handleSubmit = () => {
    const fileIds = selectedFiles.map(file => file.id);
    prepareDataMutation.mutate(fileIds);
  };

  const handleReset = () => {
    setCurrentStep(0);
    setSelectedFiles([]);
    prepareDataMutation.reset();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getStatusIcon = (step: number) => {
    if (step < currentStep) return <CheckCircleOutlined />;
    if (step === currentStep) return <SyncOutlined spin />;
    return undefined;
  };

  const steps = [
    {
      title: 'Select Files',
      description: 'Choose files to prepare for fine-tuning',
      icon: getStatusIcon(0),
    },
    {
      title: 'Review & Submit',
      description: 'Confirm selection and start processing',
      icon: getStatusIcon(1),
    },
    {
      title: 'Processing',
      description: 'Data preparation jobs are running',
      icon: getStatusIcon(2),
    },
  ];

  return (
    <Card>
      <Title level={3}>Data Preparation Wizard</Title>
      <Paragraph type="secondary">
        Follow these steps to prepare your files for fine-tuning. The system will process
        each selected file and convert it to the required format.
      </Paragraph>

      <Steps current={currentStep} items={steps} style={{ marginBottom: 24 }} />

      {/* Step 0: File Selection */}
      {currentStep === 0 && (
        <div>
          <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
            <Col>
              <Title level={4}>Select Files for Processing</Title>
              <Text type="secondary">
                Choose the files you want to prepare for fine-tuning
              </Text>
            </Col>
            <Col>
              <Space>
                <Button onClick={handleSelectAll} disabled={files.length === 0}>
                  Select All ({files.length})
                </Button>
                <Button onClick={handleClearSelection} disabled={selectedFiles.length === 0}>
                  Clear Selection
                </Button>
              </Space>
            </Col>
          </Row>

          {selectedFiles.length > 0 && (
            <Alert
              title={`${selectedFiles.length} file(s) selected`}
              description={`Total size: ${formatFileSize(
                selectedFiles.reduce((sum, file) => sum + file.bytes, 0)
              )}`}
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Error Display */}
          {filesError && (
            <div style={{ marginBottom: 16 }}>
              <QueryErrorDisplay
                error={filesErrorData}
                onRetry={() => refetchFiles()}
                showRetry={true}
              />
            </div>
          )}

          {/* Files Explorer */}
          <div>
            <Alert
              title="File Selection"
              description="Use the file explorer below to browse and select files for data preparation. Click on files to select/deselect them. You can organize files in folders and select multiple files at once."
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <FileExplorer
              files={files}
              loading={filesLoading}
              onRefresh={() => refetchFiles()}
              onUploadToFolder={() => {
                notify.info({
                  message: 'Upload from Files Page',
                  description: 'To upload new files, please go to the Files page first.'
                });
              }}
              excludeFileTypes={['jsonl','gz']}
              onUploadToRoot={() => {
                notify.info({
                  message: 'Upload from Files Page',
                  description: 'To upload new files, please go to the Files page first.'
                });
              }}
              enableSelection={true}
              onSelect={handleFileSelection}
              pathSeparator="#"
            />
          </div>
        </div>
      )}

      {/* Step 1: Review & Submit */}
      {currentStep === 1 && (
        <div>
          <Title level={4}>Review Selected Files</Title>
          <Paragraph type="secondary">
            Please review your selection before starting the data preparation process.
          </Paragraph>

          <Alert
            title="Important Information"
            description="Data preparation may take several minutes depending on file size and complexity. You can monitor progress in the jobs list."
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Card title={`Selected Files (${selectedFiles.length})`} size="small">
            <List
              dataSource={selectedFiles}
              renderItem={(file) => (
                <List.Item key={file.id}>
                  <List.Item.Meta
                    avatar={<FileOutlined />}
                    title={file.filename}
                    description={
                      <Space split={<Divider type="vertical" />}>
                        <Text type="secondary">{formatFileSize(file.bytes)}</Text>
                        <Tag color="blue">{file.purpose}</Tag>
                        <Text code>{file.id.slice(-8)}</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      )}

      {/* Step 2: Processing/Complete */}
      {currentStep === 2 && (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          {prepareDataMutation.isPending ? (
            <>
              <SyncOutlined spin style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
              <Title level={4}>Processing Files...</Title>
              <Paragraph type="secondary">
                Your data preparation jobs have been submitted and are being processed.
                This may take a few minutes.
              </Paragraph>
            </>
          ) : (
            <>
              <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
              <Title level={4}>Jobs Submitted Successfully!</Title>
              <Paragraph type="secondary">
                Your files are being processed. You can monitor progress in the jobs list.
              </Paragraph>
            </>
          )}
        </div>
      )}

      {/* Navigation Buttons */}
      <Divider />
      <Row justify="space-between">
        <Col>
          {currentStep > 0 && currentStep < 2 && (
            <Button onClick={handlePrevious} disabled={prepareDataMutation.isPending}>
              Previous
            </Button>
          )}
        </Col>
        <Col>
          <Space>
            {currentStep < 1 && (
              <Button
                type="primary"
                onClick={handleNext}
                disabled={selectedFiles.length === 0}
                icon={<RightOutlined />}
              >
                Next
              </Button>
            )}
            {currentStep === 1 && (
              <Button
                type="primary"
                onClick={handleSubmit}
                loading={prepareDataMutation.isPending}
                icon={<PlayCircleOutlined />}
              >
                Start Processing
              </Button>
            )}
            {currentStep === 2 && !prepareDataMutation.isPending && (
              <Button type="primary" onClick={handleReset}>
                Start New Process
              </Button>
            )}
          </Space>
        </Col>
      </Row>
    </Card>
  );
};

export default DataPrepWizard;
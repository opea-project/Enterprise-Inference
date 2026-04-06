'use client';

import React, { useState } from 'react';
import {
  Space,
  Typography,
  Card,
  Row,
  Col,
  Statistic,
} from 'antd';
import { notify } from '@notification';
import {
  FileTextOutlined,
} from '@ant-design/icons';
import { useFilesList } from '@features/files/hooks';
import { QueryLoading, QueryErrorDisplay } from '@/app/components';
import FileExplorer from './components/FileExplorer';
import FileUploadModal from './components/FileUploadModal';
import { config } from '@/src/core/config/appConfig';

const { Title, Text } = Typography;

const FilesPageContent: React.FC = () => {
  const [uploadModalVisible, setUploadModalVisible] = useState<boolean>(false);
  const [selectedFolder, setSelectedFolder] = useState<string>('');

  // Use TanStack Query to fetch files
  const {
    data: filesResponse,
    isLoading,
    isError,
    error,
    refetch,
    isFetching
  } = useFilesList({ limit: 100, order: 'desc' });

  const files = filesResponse?.data || [];

  // Handle upload to specific folder
  const handleUploadToFolder = (folderPath: string) => {
    setSelectedFolder(folderPath);
    setUploadModalVisible(true);
  };

  // Handle upload to root
  const handleUploadToRoot = () => {
    setSelectedFolder('');
    setUploadModalVisible(true);
  };

  // Handle upload success
  const handleUploadSuccess = () => {
    refetch(); // Refresh the file list using TanStack Query
    notify.success({ message: 'File uploaded successfully' });
  };

  // Handle upload modal cancel
  const handleUploadModalCancel = () => {
    setUploadModalVisible(false);
    setSelectedFolder('');
  };

  // Handle folder creation
  const handleFolderCreated = () => {
    // You could potentially create a marker file here if needed
    // For now, the folder will be visible in the tree and functional for uploads
  };

  // Format bytes to human readable
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Calculate statistics
  const totalFiles = files.length;
  const totalSize = files.reduce((sum, file) => sum + file.bytes, 0);
  const purposeCounts = files.reduce((acc, file) => {
    acc[file.purpose] = (acc[file.purpose] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div style={{ padding: '24px', height: '100vh' }}>
      <Space orientation="vertical" size="large" style={{ width: '100%', height: '100%' }}>
        {/* Header */}
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={2}>Files Management</Title>
            <Text type="secondary">
              Manage files for Data Preparation and Fine-Tuning jobs.
            </Text>
          </Col>
        </Row>

        {/* Statistics */}
        <Row gutter={16}>
          <Col span={8}>
            <Card>
              <Statistic
                title="Total Files"
                value={totalFiles}
                prefix={<FileTextOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="Total Storage"
                value={formatBytes(totalSize)}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="File Types"
                value={Object.keys(purposeCounts).length}
              />
            </Card>
          </Col>
        </Row>

        {/* Error Display */}
        {isError && (
          <QueryErrorDisplay
            error={error}
            onRetry={() => refetch()}
            showRetry={true}
          />
        )}

        {/* File Explorer */}
        <QueryLoading
          isLoading={isLoading}
          isFetching={isFetching}
          loadingType="skeleton"
          skeletonType="list"
          skeletonRows={5}
        >
          <div style={{ flex: 1, minHeight: 0 }}>
            <FileExplorer
              files={files}
              loading={isLoading || isFetching}
              onRefresh={() => refetch()}
              onUploadToFolder={handleUploadToFolder}
              onUploadToRoot={handleUploadToRoot}
              onFolderCreated={handleFolderCreated}
              enableSelection={false}
              onSelect={() => {}}
            />
          </div>
        </QueryLoading>
      </Space>

      {/* Upload Modal */}
      <FileUploadModal
        visible={uploadModalVisible}
        onCancel={handleUploadModalCancel}
        onSuccess={handleUploadSuccess}
        pathSeparator={config.filePathSeperator}
        currentFolder={selectedFolder}
      />
    </div>
  );
};

const FilesPage: React.FC = () => {
  return <FilesPageContent />;
};

export default FilesPage;
'use client';

import React from 'react';
import { Typography, Button, Space, App } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useFileName, useDownloadFile } from '@features/files/hooks';

const { Text } = Typography;

interface FileNameDisplayProps {
  fileId: string;
  showDownload?: boolean;
}

// Component to display filename instead of file ID
const FileNameDisplay: React.FC<FileNameDisplayProps> = ({
  fileId,
  showDownload = false
}) => {
  const { message } = App.useApp();

  // All hooks must be called before any conditional returns
  const { data: filename, isLoading } = useFileName(fileId);

  const downloadFile = useDownloadFile({
    onSuccess: () => {
      message.success('Download started');
    },
    onError: (error: Error) => {
      message.error(`Download failed: ${error.message}`);
    },
  });

  // Return early if fileId is empty (after all hooks are called)
  if (!fileId) {
    return <Text type="secondary">File not available</Text>;
  }

  const handleDownload = () => {
    downloadFile.mutate({
      fileId,
      filename: filename || undefined
    });
  };

  if (isLoading) {
    return <Text code type="secondary">Loading filename...</Text>;
  }

  const filenameDisplay = (
    <Text code title={`${filename || fileId}`} ellipsis={true}>
      {filename || fileId}
    </Text>
  );

  if (!showDownload) {
    return filenameDisplay;
  }

  return (
    <Space size="small">
      {filenameDisplay}
      <Button
        type="text"
        size="small"
        icon={<DownloadOutlined />}
        onClick={handleDownload}
        loading={downloadFile.isPending}
        title="Download file"
        style={{ padding: '0 4px', border:'1px solid #d9d9d9' }}
      />
    </Space>
  );
};

export default FileNameDisplay;
'use client';

import React, { useState, useCallback } from 'react';
import { Modal, Button, Typography, Empty, Spin } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { useFilesList } from '@features/files/hooks';
import { FileObject } from '@features/files/types';
import { FileExplorer } from '../files/components';

const { Text } = Typography;

interface FileSelectionModalProps {
  visible: boolean;
  onCancel: () => void;
  onSelect: (file: FileObject) => void;
  title?: string;
  description?: string;
  showOnlyFileTypes?: string[];
  excludeFileTypes?: string[];
  maxSelection?: number;
  displaySelectedFile?: boolean;
}

const FileSelectionModal: React.FC<FileSelectionModalProps> = ({
  visible,
  onCancel,
  onSelect,
  title = 'Select File',
  description = 'Please select a file from the list below.',
  showOnlyFileTypes = [],
  excludeFileTypes = [],
  maxSelection = 1,
  displaySelectedFile = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<FileObject | null>(null);

  // Fetch files
  const { data: filesResponse, isLoading, refetch } = useFilesList(
    undefined,
    { enabled: visible }
  );

  const files = filesResponse?.data || [];

  // Handle file selection from FileExplorer
  const handleFileSelect = useCallback((selectedFiles: FileObject[]) => {
    // Only allow single file selection - replace current selection
    if (selectedFiles.length > 0) {
      setSelectedFile(selectedFiles[0]);
    } else {
      setSelectedFile(null);
    }
  }, []);

  // Handle confirm selection
  const handleConfirm = useCallback(() => {
    if (selectedFile) {
      onSelect(selectedFile);
      setSelectedFile(null);
    }
  }, [selectedFile, onSelect]);

  // Handle cancel
  const handleCancel = useCallback(() => {
    setSelectedFile(null);
    onCancel();
  }, [onCancel]);

  return (
    <Modal
      title={title}
      open={visible}
      onCancel={handleCancel}
      width={1500}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          Cancel
        </Button>,
        <Button
          key="select"
          type="primary"
          disabled={!selectedFile}
          onClick={handleConfirm}
        >
          Select File
        </Button>,
      ]}
      styles={{
        body: {
          height: '500px',
          overflow: 'hidden',
          padding: 0,
        },
      }}
    >
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Description */}
        {description && (
          <div style={{ padding: '16px 24px 0 24px' }}>
            <Text type="secondary">{description}</Text>
          </div>
        )}

        {/* Selected file display */}
        {displaySelectedFile && selectedFile && (
          <div
            style={{
              padding: '12px 24px',
              marginTop: '12px',
              background: '#f0f8ff',
              borderBottom: '1px solid #d9d9d9',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <FileTextOutlined style={{ color: '#1890ff' }} />
            <Text strong>Selected: </Text>
            <Text code>{selectedFile.filename}</Text>
            <Text type="secondary">({selectedFile.id})</Text>
          </div>
        )}


        {/* File Explorer */}
        <div style={{ flex: 1, overflow: 'hidden', padding: '24px 24px 24px 24px' }}>
          {isLoading ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Spin size="large" />
            </div>
          ) : files.length === 0 ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Empty
                description="No files available"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </div>
          ) : (
            <FileExplorer
              files={files}
              loading={false}
              onRefresh={refetch}
              onUploadToFolder={() => {}}
              onUploadToRoot={() => {}}
              enableSelection={true}
              onSelect={handleFileSelect}
              maxSelection={maxSelection}
              showOnlyFileTypes={showOnlyFileTypes}
              excludeFileTypes={excludeFileTypes}
            />
          )}
        </div>
      </div>
    </Modal>
  );
};

export default FileSelectionModal;
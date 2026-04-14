'use client';

import React, { useState } from 'react';
import {
  Modal,
  Upload,
  Button,
  Select,
  Space,
  Typography,
  Input,
} from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { notify } from '@notification';
import { useUploadFile } from '@features/files/hooks';
import { FilePurpose } from '@features/files/types';
import { config } from '@/src/core/config/appConfig';

const { Text } = Typography;
const { Option } = Select;

interface FileUploadModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  currentFolder?: string; // Current folder path for uploads
  pathSeparator?: string; // Separator for folder paths (default: '#')
}

const FileUploadModal: React.FC<FileUploadModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  currentFolder = '',
  pathSeparator = config.filePathSeperator,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedPurpose, setSelectedPurpose] = useState<FilePurpose>('fine-tune');
  const [uploading, setUploading] = useState<boolean>(false);
  const [customFileName, setCustomFileName] = useState<string>('');
  const [fileList, setFileList] = useState<any[]>([]);

  // Upload file mutation hook
  const uploadFileMutation = useUploadFile();

  // Format bytes to human readable
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Handle file upload
  const handleUpload = async () => {
    if (!selectedFile) {
      notify.error({ message: 'Please select a file' });
      return;
    }

    // Validate file type for specific purposes
    const requiresJsonl = ['fine-tune', 'evals', 'batch'].includes(selectedPurpose);
    if (requiresJsonl && !selectedFile.name.toLowerCase().endsWith('.jsonl')) {
      notify.error({ message: 'Please select a .jsonl file for this purpose' });
      return;
    }

    setUploading(true);
    try {
      // Create the filename with folder path if in a folder
      const fileName = customFileName || selectedFile.name;
      const fullFileName = currentFolder ? `${currentFolder}${pathSeparator}${fileName}` : fileName;



      // Create a new File object with the modified name
      const fileToUpload = new File([selectedFile], fullFileName, {
        type: selectedFile.type,
        lastModified: selectedFile.lastModified,
      });

      await uploadFileMutation.mutateAsync({
        file: fileToUpload,
        purpose: selectedPurpose
      });
      handleCancel();
      onSuccess(); // Refresh the file list
    } catch (error) {
      notify.error({ message: error instanceof Error ? error.message : 'Failed to upload file' });
    } finally {
      setUploading(false);
    }
  };

  // Handle modal cancel
  const handleCancel = () => {
    setSelectedFile(null);
    setCustomFileName('');
    setFileList([]);
    onCancel();
  };

  return (
    <Modal
      title={`Upload File${currentFolder ? ` to ${currentFolder}` : ''}`}
      open={visible}
      onOk={handleUpload}
      onCancel={handleCancel}
      confirmLoading={uploading}
      okText="Upload"
      width={600}
    >
      <Space orientation="vertical" style={{ width: '100%' }}>
        {/* Current folder display */}
        {currentFolder && (
          <div style={{ padding: 12, background: '#f0f2f5', borderRadius: 4 }}>
            <Text strong>Uploading to folder: </Text>
            <Text code>{currentFolder}</Text>
          </div>
        )}

        {/* File purpose selection */}
        <div>
          <Text strong>Select File Purpose:</Text>
          <Select
            value={selectedPurpose}
            onChange={setSelectedPurpose}
            style={{ width: '100%', marginTop: 8 }}
          >
            <Option value="fine-tune">Fine-tune (.jsonl)</Option>
            {/* <Option value="evals">Evals (.jsonl)</Option> */}
            {/* <Option value="batch">Batch API (.jsonl, max 200 MB)</Option> */}
            {/* <Option value="assistants">Assistants (up to 2M tokens)</Option> */}
            {/* <Option value="vision">Vision (images for fine-tuning)</Option> */}
            <Option value="user_data">User Data (flexible)</Option>
          </Select>
        </div>

        {/* File selection */}
        <div>
          <Text strong>Select File:</Text>
          <Upload
            maxCount={1}
            fileList={fileList}
            accept={['fine-tune', 'evals', 'batch'].includes(selectedPurpose) ? '.jsonl' : '.txt, .pdf, .json, .jsonl, .tar.gz, .docx, .pptx'}
            beforeUpload={(file) => {
              setSelectedFile(file);
              setCustomFileName(''); // Reset custom name when new file is selected
              setFileList([{
                uid: file.uid || '-1',
                name: file.name,
                status: 'done',
                originFileObj: file,
              }]);
              return false; // Prevent auto upload
            }}
            onRemove={() => {
              setSelectedFile(null);
              setCustomFileName('');
              setFileList([]);
            }}
            style={{ marginTop: 8 }}
          >
            <Button icon={<UploadOutlined />}>
              Choose File
            </Button>
          </Upload>
        </div>

        {/* Custom filename input */}
        {selectedFile && (
          <div>
            <Text strong>File Name (optional):</Text>
            <Input
              placeholder={selectedFile.name}
              value={customFileName}
              onChange={(e) => setCustomFileName(e.target.value)}
              style={{ marginTop: 8 }}
              addonBefore={currentFolder ? `${currentFolder}${pathSeparator}` : undefined}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
              Leave empty to use original filename
            </Text>
          </div>
        )}

        {/* Selected file info */}
        {selectedFile && (
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">
              Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
            </Text>
            {/* {currentFolder && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary">
                  Will be saved as: <Text code style={{ color: '#1890ff' }}>{currentFolder}{pathSeparator}{customFileName || selectedFile.name}</Text>
                </Text>
              </div>
            )} */}
          </div>
        )}

        {/* File limits info */}
        <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <strong>Limits:</strong><br />
            • Individual files: up to 512 MB<br />
            {/* • Batch API: .jsonl files up to 200 MB<br />
            • Assistants: files up to 2 million tokens<br /> */}
            • Fine-tuning: .jsonl files only<br />
            • User Data: .txt, .pdf, .json, .jsonl, .tar.gz, .docx, .pptx only

          </Text>
        </div>
      </Space>
    </Modal>
  );
};

export default FileUploadModal;
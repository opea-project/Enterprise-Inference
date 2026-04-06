'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, Form, Input, Select, InputNumber, Button, Space, Typography, Alert, Divider } from 'antd';
import { ArrowLeftOutlined, PlusOutlined, FileTextOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { useCreateFineTuningJob, useModels } from '@features/finetuning';
import { CreateFineTuningJobRequest } from '@features/finetuning/types';
import FileSelectionModal from '@components/FileSelectionModal';
import { FileObject } from '@features/files/types';

const { Title, Text } = Typography;
const { Option } = Select;

type ResourceType = 'xeon' | 'nvidia' | 'aws';

interface HyperparameterFormValues {
  n_epochs?: number;
  batch_size?: number;
  learning_rate_multiplier?: number;
}

interface FineTuningFormValues {
  model: string;
  training_file: string;
  validation_file?: string;
  hyperparameters?: HyperparameterFormValues;
  suffix?: string;
  resource_type?: ResourceType;
}

const NewFineTuningJobPage = () => {
  const router = useRouter();
  const [form] = Form.useForm();
  const [trainingFileModalVisible, setTrainingFileModalVisible] = useState(false);
  const [validationFileModalVisible, setValidationFileModalVisible] = useState(false);
  const [selectedTrainingFile, setSelectedTrainingFile] = useState<FileObject | null>(null);
  const [selectedValidationFile, setSelectedValidationFile] = useState<FileObject | null>(null);
  const errorAlertRef = useRef<HTMLDivElement>(null);

  const { data: modelsData, isLoading: modelsLoading, error: modelsError } = useModels();

  const createFineTuningJobMutation = useCreateFineTuningJob({
    onSuccess: () => {
      router.push('/finetuning');
    },
    onError: () => {
      // Error handled by mutation
    },
  });

  const handleSubmit = async (values: FineTuningFormValues) => {
    const request: CreateFineTuningJobRequest = {
      model: values.model,
      training_file: values.training_file,
      validation_file: values.validation_file || null,
      hyperparameters: values.hyperparameters ? {
        n_epochs: values.hyperparameters.n_epochs || null,
        batch_size: values.hyperparameters.batch_size || null,
        learning_rate_multiplier: values.hyperparameters.learning_rate_multiplier || null,
      } : null,
      suffix: values.suffix || null,
      resource_type: values.resource_type || 'xeon',
    };

    createFineTuningJobMutation.mutate(request);
  };

  const handleCancel = () => {
    router.push('/finetuning');
  };

  const handleTrainingFileSelect = (file: FileObject) => {
    setSelectedTrainingFile(file);
    form.setFieldsValue({ training_file: file.id });
    setTrainingFileModalVisible(false);
  };

  const handleValidationFileSelect = (file: FileObject) => {
    setSelectedValidationFile(file);
    form.setFieldsValue({ validation_file: file.id });
    setValidationFileModalVisible(false);
  };

  const handleRemoveTrainingFile = () => {
    setSelectedTrainingFile(null);
    form.setFieldsValue({ training_file: undefined });
  };

  const handleRemoveValidationFile = () => {
    setSelectedValidationFile(null);
    form.setFieldsValue({ validation_file: undefined });
  };

  useEffect(() => {
    if (createFineTuningJobMutation.isError && errorAlertRef.current) {
      errorAlertRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      errorAlertRef.current.focus();
    }
  }, [createFineTuningJobMutation.isError]);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleCancel}
          style={{ marginBottom: 16 }}
        >
          Back to Fine-Tuning Jobs
        </Button>
        <Title level={2}>Create Fine-Tuning Job</Title>
        <Text type="secondary">
          Create a new fine-tuning job using the OpenAI compatible API
        </Text>
      </div>

      <Alert
        title="Resource Constraints"
        description="Please note that compute resources are limited. If resources are already running at capacity, you may encounter errors when creating a fine-tuning job. Please try again later if this occurs."
        type="warning"
        showIcon
        style={{ marginBottom: 24 }}
      />

      {createFineTuningJobMutation.isError && (
        <div ref={errorAlertRef} tabIndex={-1} style={{ outline: 'none' }}>
          <Alert
            title="Error Creating Job"
            description={createFineTuningJobMutation.error?.message || 'Failed to create fine-tuning job'}
            type="error"
            showIcon
            closable
            onClose={() => createFineTuningJobMutation.reset()}
            style={{ marginBottom: 24 }}
          />
        </div>
      )}

      {modelsError && (
        <Alert
          title="Error Loading Models"
          description={modelsError?.message || 'Failed to load available models'}
          type="warning"
          showIcon
          closable
          style={{ marginBottom: 24 }}
        />
      )}

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            resource_type: 'nvidia',
            hyperparameters: {
              n_epochs: null,
              batch_size: null,
              learning_rate_multiplier: null,
            },
          }}
        >
          <Title level={4}>Basic Configuration</Title>

          <Form.Item
            label="Base Model"
            name="model"
            rules={[{ required: true, message: 'Please select a model' }]}
            extra="The name of the model to fine-tune. You can select from available models."
          >
            <Select
              placeholder="Select a model"
              loading={modelsLoading}
              notFoundContent={modelsError ? 'Error loading models' : 'No models available'}
            >
              {modelsData?.data?.map((model) => (
                <Option key={model.id} value={model.id}>
                  {model.id} {model.owned_by && `(${model.owned_by})`}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="Training File"
            name="training_file"
            rules={[{ required: true, message: 'Please select a training file' }]}
            extra="Select an uploaded file that contains training data."
          >
            <div>
              {selectedTrainingFile ? (
                <div style={{
                  border: '1px solid #d9d9d9',
                  borderRadius: 6,
                  padding: 12,
                  background: '#fafafa',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileTextOutlined style={{ color: '#52c41a' }} />
                    <div>
                      <div style={{ fontWeight: 500 }}>{selectedTrainingFile.filename}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>ID: {selectedTrainingFile.id}</div>
                    </div>
                  </div>
                  <Button
                    size="small"
                    danger
                    onClick={handleRemoveTrainingFile}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <Button
                  icon={<FileTextOutlined />}
                  onClick={() => setTrainingFileModalVisible(true)}
                  style={{ width: '100%' }}
                >
                  Select Training File
                </Button>
              )}
            </div>
          </Form.Item>

          <Form.Item
            label="Validation File"
            name="validation_file"
            extra="Optional. Select an uploaded file that contains validation data."
            hidden={true}
          >
            <div>
              {selectedValidationFile ? (
                <div style={{
                  border: '1px solid #d9d9d9',
                  borderRadius: 6,
                  padding: 12,
                  background: '#fafafa',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileTextOutlined style={{ color: '#52c41a' }} />
                    <div>
                      <div style={{ fontWeight: 500 }}>{selectedValidationFile.filename}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>ID: {selectedValidationFile.id}</div>
                    </div>
                  </div>
                  <Button
                    size="small"
                    danger
                    onClick={handleRemoveValidationFile}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <Button
                  icon={<FileTextOutlined />}
                  onClick={() => setValidationFileModalVisible(true)}
                  style={{ width: '100%' }}
                >
                  Select Validation File (Optional)
                </Button>
              )}
            </div>
          </Form.Item>

          <Form.Item
            label="Resource Type"
            name="resource_type"
            extra="The type of compute resource to use for fine-tuning."
          >
            <Select>
              <Option value="nvidia">Nvidia GPU Engine</Option>
              <Option value="xeon" disabled>Intel Xeon (Coming Soon)</Option>
              <Option value="aws" disabled>Amazon AWS (Coming Soon)</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="Suffix"
            name="suffix"
            extra="Optional. A string of up to 64 characters that will be added to your fine-tuned model name."
          >
            <Input placeholder="my-fine-tuned-model" maxLength={64} />
          </Form.Item>

          <Divider />

          <Title level={4}>Hyperparameters</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            Customize the training hyperparameters. Leave blank to use defaults.
          </Text>

          <Form.Item>
            <Input.Group compact>
              <Form.Item
                name={['hyperparameters', 'n_epochs']}
                label="Epochs"
                style={{ display: 'inline-block', width: 'calc(33.33% - 8px)', marginRight: 8 }}
              >
                <InputNumber
                  placeholder="Epochs (3)"
                  min={1}
                  max={3}
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item
                name={['hyperparameters', 'batch_size']}
                label="Batch Size"
                style={{ display: 'inline-block', width: 'calc(33.33% - 8px)', marginRight: 8 }}
              >
                <InputNumber
                  placeholder="Batch Size (4)"
                  min={1}
                  max={4}
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item
                name={['hyperparameters', 'learning_rate_multiplier']}
                label="Learning Rate"
                style={{ display: 'inline-block', width: 'calc(33.33% - 8px)' }}
              >
                <InputNumber
                  placeholder="Learning Rate (1.0)"
                  min={0.01}
                  max={2}
                  step={0.01}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Input.Group>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                Epochs: Number of training cycles | Batch Size: Training batch size | Learning Rate: Learning rate multiplier
              </Text>
            </div>
          </Form.Item>

          <Divider />

          <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={createFineTuningJobMutation.isPending}
                icon={<PlusOutlined />}
                size="large"
              >
                Create Fine-Tuning Job
              </Button>
              <Button onClick={handleCancel} size="large">
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {/* Training File Selection Modal */}
      <FileSelectionModal
        visible={trainingFileModalVisible}
        onCancel={() => setTrainingFileModalVisible(false)}
        onSelect={handleTrainingFileSelect}
        title="Select Training File"
        description="Choose a file that contains your training data. The file should be in JSONL format for fine-tuning."
        showOnlyFileTypes={['jsonl']}
        maxSelection={1}
      />

      {/* Validation File Selection Modal */}
      <FileSelectionModal
        visible={validationFileModalVisible}
        onCancel={() => setValidationFileModalVisible(false)}
        onSelect={handleValidationFileSelect}
        title="Select Validation File"
        description="Choose an optional file that contains your validation data. The file should be in JSONL format."
        showOnlyFileTypes={['jsonl']}
        maxSelection={1}
      />
    </div>
  );
};

export default NewFineTuningJobPage;
'use client';

import React from 'react';
import { Button, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { DataPrepWizard } from '../components';

const { Title, Text } = Typography;

const NewDataPrepPage = () => {
  const router = useRouter();

  const handleCancel = () => {
    router.push('/dataprep');
  };

  const handleJobsCreated = () => {
    router.push('/dataprep');
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleCancel}
          style={{ marginBottom: 16 }}
        >
          Back to Data Preparation
        </Button>
        <Title level={2}>Create Data Preparation Job</Title>
        <Text type="secondary">
          Process your data files for fine-tuning by converting them to the required format
        </Text>
      </div>

      <DataPrepWizard onJobsCreated={handleJobsCreated} />
    </div>
  );
};

export default NewDataPrepPage;
'use client';

import React from 'react';
import { Typography } from 'antd';
import { DataPrepJobsList } from './components';

const { Title } = Typography;

const DataPrepPage = () => {
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>
        Data Preparation Jobs
      </Title>

      <DataPrepJobsList />
    </div>
  );
};

export default DataPrepPage;
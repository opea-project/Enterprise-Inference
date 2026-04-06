'use client';

import React, { useMemo } from 'react';
import { Button, Typography, Card, Row, Col } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useRouter, useParams } from 'next/navigation';
import { useJobStatus, useDataPrepJobs } from '@features/dataprep/hooks';
import { QueryLoading, QueryErrorDisplay } from '@/app/components';
import { DataPrepJobDetails } from '../components';

const { Title, Text } = Typography;

const DataPrepJobPage = () => {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  // Get all jobs to find the complete job data
  const { data: jobsResponse } = useDataPrepJobs();

  // Also get the job status for real-time updates
  const {
    data: jobStatus,
    isLoading,
    isError,
    error,
    refetch
  } = useJobStatus(jobId);

  const handleBack = () => {
    router.push('/dataprep');
  };

  const handleRefresh = () => {
    refetch();
  };

  // Find the complete job data from the jobs list, or create one from status
  const jobWithStatus = useMemo(() => {
    if (!jobId) return null;

    // First, try to find the job in the jobs list (has complete data)
    const fullJob = jobsResponse?.jobs?.find(job => job.job_id === jobId);
    if (fullJob) {
      return fullJob;
    }

    // If not found in jobs list, create from status (might be incomplete)
    if (jobStatus) {
      return {
        job_id: jobStatus.job_id,
        status: jobStatus.status,
        result: jobStatus.result,
        error: jobStatus.error,
        // These fields might not be available from the status endpoint
        user_id: '',
        file_id: '',
        submitted_at: new Date().toISOString(),
        metadata: {}
      };
    }

    return null;
  }, [jobId, jobsResponse?.jobs, jobStatus]);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          style={{ marginBottom: 16 }}
        >
          Back to Data Preparation Jobs
        </Button>
        <Title level={2}>Data Preparation Job Details</Title>
        <Text type="secondary">
          Job ID: <Text code>{jobId}</Text>
        </Text>
      </div>

      {/* Error Display */}
      {isError && (
        <QueryErrorDisplay
          error={error}
          onRetry={handleRefresh}
          showRetry={true}
        />
      )}

      <QueryLoading
        isLoading={isLoading}
        loadingType="skeleton"
        skeletonType="card"
      >
        {jobWithStatus ? (
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <DataPrepJobDetails
                job={jobWithStatus}
                onRefresh={handleRefresh}
              />
            </Col>
          </Row>
        ) : (
          <Card>
            <Text type="secondary">Job not found or failed to load.</Text>
          </Card>
        )}
      </QueryLoading>
    </div>
  );
};

export default DataPrepJobPage;
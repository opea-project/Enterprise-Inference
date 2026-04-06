'use client';

import React, { useState, useMemo } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Progress,
  Tooltip,
  Typography,
  Row,
  Col,
  Statistic,
  Select,
  Input,
  Popover,
} from 'antd';
import {
  ReloadOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  SearchOutlined,
  FilterOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TableProps } from 'antd/es/table';
import { useRouter } from 'next/navigation';
import { useDataPrepJobs, useDataPrepUtilities } from '@features/dataprep/hooks';
import { QueryLoading, QueryErrorDisplay } from '@/app/components';
import type { JobWithStatus, JobStatus } from '@features/dataprep/types';
import { DataPrepStatus } from '@features/dataprep/types';
import { FileNameDisplay } from '@/app/files/components';

const { Text } = Typography;
const { Option } = Select;
const { Search } = Input;

interface DataPrepJobsListProps {
  onJobSelect?: (job: JobWithStatus) => void;
  selectedJobId?: string;
}

const DataPrepJobsList: React.FC<DataPrepJobsListProps> = ({
  onJobSelect,
  selectedJobId,
}) => {
  const router = useRouter();
  const [searchText, setSearchText] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'all'>('all');
  const [pageSize, setPageSize] = useState<number>(10);

  const {
    data: jobsResponse,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useDataPrepJobs();

  const {
    isJobActive,
    isJobComplete,
    formatJobDuration,
    getJobStatusColor,
    getActiveJobs,
    getCompletedJobs,
  } = useDataPrepUtilities();

  const jobs = useMemo(() => jobsResponse?.jobs || [], [jobsResponse?.jobs]);

  // Filter and search jobs
  const filteredJobs = useMemo(() => {
    let filtered = jobs;

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter(job =>
        job.status === statusFilter
      );
    }

    // Filter by search text
    if (searchText) {
      const searchLower = searchText.toLowerCase();
      filtered = filtered.filter(job =>
        job.job_id.toLowerCase().includes(searchLower) ||
        job.file_id.toLowerCase().includes(searchLower) ||
        job.status.toLowerCase().includes(searchLower)
      );
    }

    return filtered.sort((a, b) =>
      new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime()
    );
  }, [jobs, searchText, statusFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const active = getActiveJobs(jobs);
    const completed = getCompletedJobs(jobs);
    const failed = jobs.filter(job =>
      job.status === DataPrepStatus.FAILURE
    );

    return {
      total: jobs.length,
      active: active.length,
      completed: completed.length,
      failed: failed.length,
    };
  }, [jobs, getActiveJobs, getCompletedJobs]);

  const columns: ColumnsType<JobWithStatus> = [
    {
      title: 'Job ID',
      dataIndex: 'job_id',
      key: 'job_id',
      width: 120,
      render: (jobId: string) => (
        <Button
          type="link"
          style={{ padding: 0, fontSize: '12px' }}
          onClick={() => router.push(`/dataprep/${jobId}`)}
        >
          <Typography.Text code style={{ fontSize: '12px' }}>
            {jobId.slice(-8)}
          </Typography.Text>
        </Button>
      ),
    },
    {
      title: 'Input File',
      dataIndex: 'file_id',
      key: 'file_id',
      width: 120,
      render: (fileId: string) => {
        if (fileId.includes(',')) {
          const fileIds = fileId.split(',').map(id => id.trim());
          const count = fileIds.length;
          const content = (
            <Space orientation="vertical" size="small" style={{ maxWidth: 300 }}>
              {fileIds.map((id: string) => (
                <FileNameDisplay key={id} fileId={id} />
              ))}
            </Space>
          );
          return (
            <Popover content={content} title={`${count} Input Files`} trigger="hover">
              <Space size={4}>
                <FileNameDisplay fileId={fileIds[0]} />
                <Tag color="blue" style={{ fontSize: '11px', padding: '0 4px', cursor: 'pointer' }}>
                  +{count - 1} more
                </Tag>
              </Space>
            </Popover>
          );
        }
        return <FileNameDisplay fileId={fileId} />;
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const color = getJobStatusColor(status);
        return (
          <Tag color={color} icon={isJobActive(status) ? <PlayCircleOutlined /> : undefined}>
            {status.toUpperCase()}
          </Tag>
        );
      },
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 120,
      render: (_, record) => {
        const status = record.status;
        if (status === DataPrepStatus.SUCCESS) {
          return <Progress percent={100} size="small" status="success" />;
        }
        if (status === DataPrepStatus.FAILURE) {
          return <Progress percent={100} size="small" status="exception" />;
        }
        if (status === DataPrepStatus.PROCESSING) {
          // Show indeterminate progress for processing
          return <Progress percent={60} size="small" status="active" />;
        }
        return <Progress percent={0} size="small" />;
      },
    },
    {
      title: 'Submitted',
      dataIndex: 'submitted_at',
      key: 'submitted_at',
      width: 150,
      render: (submittedAt: string) => {
        const date = new Date(submittedAt);
        return (
          <Tooltip title={date.toLocaleString()}>
            <Text type="secondary">
              {date.toLocaleDateString()} {date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit'
              })}
            </Text>
          </Tooltip>
        );
      },
    },
    {
      title: 'Duration',
      key: 'duration',
      hidden: true,
      width: 100,
      render: (_, record) => {
        if (isJobComplete(record.status)) {
          // For completed/failed jobs, we'd need an end time
          // For now, show submitted time duration
          return (
            <Text type="secondary">
              {formatJobDuration(record.submitted_at)}
            </Text>
          );
        }
        if (isJobActive(record.status)) {
          return (
            <Text type="secondary">
              {formatJobDuration(record.submitted_at)}
            </Text>
          );
        }
        return <Text type="secondary">-</Text>;
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => router.push(`/dataprep/${record.job_id}`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const tableProps: TableProps<JobWithStatus> = {
    columns,
    dataSource: filteredJobs,
    rowKey: 'job_id',
    size: 'small',
    pagination: {
      pageSize,
      showSizeChanger: true,
      showQuickJumper: true,
      showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} jobs`,
      onShowSizeChange: (_, size) => setPageSize(size),
    },
    rowSelection: selectedJobId ? {
      type: 'radio',
      selectedRowKeys: [selectedJobId],
      onSelect: (record) => onJobSelect?.(record),
    } : undefined,
    // loading: isLoading || isFetching, // double loading icon on refresh
  };

  return (
    <Card>
      {/* Statistics */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Active Jobs"
              value={stats.active}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Completed"
              value={stats.completed}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Failed"
              value={stats.failed}
              styles={{ content: { color: '#ff4d4f' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Total"
              value={stats.total}
            />
          </Card>
        </Col>
      </Row>

      {/* Action Buttons */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => router.push('/dataprep/new')}
          >
            Create Data Prep Job
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            Refresh
          </Button>
        </Space>
      </div>

      {/* Filters */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Search
            placeholder="Search by Job ID, File ID, or Status"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
            prefix={<SearchOutlined />}
          />
        </Col>
        <Col span={8}>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: '100%' }}
            placeholder="Filter by status"
            suffixIcon={<FilterOutlined />}
          >
            <Option value="all">All Statuses</Option>
            <Option value={DataPrepStatus.PROCESSING}>Processing</Option>
            <Option value={DataPrepStatus.SUCCESS}>Success</Option>
            <Option value={DataPrepStatus.FAILURE}>Failure</Option>
          </Select>
        </Col>
      </Row>

      {/* Error Display */}
      {isError && (
        <div style={{ marginBottom: 16 }}>
          <QueryErrorDisplay
            error={error}
            onRetry={() => refetch()}
            showRetry={true}
          />
        </div>
      )}

      {/* Jobs Table */}
      <QueryLoading
        isLoading={isLoading}
        isFetching={isFetching}
        loadingType="skeleton"
        skeletonType="table"
        skeletonRows={5}
      >
        <Table {...tableProps} />
      </QueryLoading>
    </Card>
  );
};

export default DataPrepJobsList;
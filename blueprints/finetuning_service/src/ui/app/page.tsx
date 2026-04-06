'use client';

import { Button, Card, Typography, Divider, Row, Col, Statistic, Space } from 'antd';
import { PlusOutlined, ExperimentOutlined, FolderOutlined, FileTextOutlined, EyeOutlined} from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { useFilesList } from '@features/files/hooks';
import { useFineTuningJobsList } from '@features/finetuning/hooks';
import { useDataPrepJobs } from '@features/dataprep/hooks';

const { Title, Paragraph } = Typography;


export default function Home() {
  const router = useRouter();

  // Fetch data for stats
  const { data: filesData, isLoading: filesLoading } = useFilesList();
  const { data: fineTuningData, isLoading: fineTuningLoading } = useFineTuningJobsList();
  const { data: dataPrepData, isLoading: dataPrepLoading } = useDataPrepJobs();

  const totalFiles = filesData?.data?.length || 0;
  const totalFineTuningJobs = fineTuningData?.data?.length || 0;
  const totalDataPrepJobs = dataPrepData?.total_jobs || 0;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>Dashboard</Title>
      <Paragraph>
        Welcome to your Fine-tuning Dashboard! Here you can manage your files and fine-tune your models efficiently.
      </Paragraph>

      <Divider />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8}>
          <Card
            title="Files"
            extra={<FolderOutlined />}
            style={{ height: '100%' }}
          >
            <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
              <Statistic
                title="Total Files"
                value={totalFiles}
                loading={filesLoading}
              />
              <Paragraph>Manage your files and datasets for fine-tuning.</Paragraph>
              <Button
                type="primary"
                icon={<EyeOutlined />}
                onClick={() => router.push('/files')}
              >
                View Files
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={8}>
          <Card
            title="Data Preparation"
            extra={<FileTextOutlined />}
            style={{ height: '100%' }}
          >
            <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
              <Statistic
                title="Total Jobs"
                value={totalDataPrepJobs}
                loading={dataPrepLoading}
              />
              <Paragraph>Convert raw data into fine-tuning ready JSONL format.</Paragraph>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => router.push('/dataprep/new')}
              >
                New Data Prep Job
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={8}>
          <Card
            title="Fine-Tuning"
            extra={<ExperimentOutlined />}
            style={{ height: '100%' }}
          >
            <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
              <Statistic
                title="Total Jobs"
                value={totalFineTuningJobs}
                loading={fineTuningLoading}
              />
              <Paragraph>Fine-Tune your models with ease.</Paragraph>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => router.push('/finetuning/new')}
              >
                New Fine-Tuning Job
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <Divider />



      {/* <Space>
        <Button type="primary">Primary Button</Button>
        <Button>Default Button</Button>
        <Button type="dashed">Dashed Button</Button>
        <Button type="text">Text Button</Button>
      </Space> */}
    </div>
  );
}

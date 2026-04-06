import {
  FineTuningJob,
  FineTuningJobStatus,
  FineTuningJobDisplay,
  FineTuningHyperparameters,
} from '../types';

export const transformFineTuningJobForDisplay = (job: FineTuningJob): FineTuningJobDisplay => {
  const displayName = `Fine-tune ${job.model} - ${job.id.substring(0, 8)}`;
  const displayStatus = getFineTuningStatusText(job.status);
  const displayProgress = getFineTuningProgress(job.status);
  const displayModel = job.model.split('/').pop() || job.model;
  const displayDataset = job.training_file || 'Unknown Dataset';

  return {
    ...job,
    key: job.id,
    displayName,
    displayStatus,
    displayProgress,
    displayModel,
    displayDataset,
  };
};

export const getFineTuningStatusColor = (status: FineTuningJobStatus): string => {
  switch (status) {
    case 'validating_files':
      return 'blue';
    case 'queued':
      return 'orange';
    case 'running':
      return 'processing';
    case 'succeeded':
      return 'success';
    case 'failed':
      return 'error';
    case 'cancelled':
      return 'default';
    default:
      return 'default';
  }
};

export const getFineTuningStatusText = (status: FineTuningJobStatus): string => {
  switch (status) {
    case 'validating_files':
      return 'Validating Files';
    case 'queued':
      return 'Queued';
    case 'running':
      return 'Running';
    case 'succeeded':
      return 'Succeeded';
    case 'failed':
      return 'Failed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return `${status}`.charAt(0).toUpperCase() + `${status}`.slice(1);
  }
};

export const getFineTuningProgress = (status: FineTuningJobStatus): number => {
  switch (status) {
    case 'validating_files':
      return 10;
    case 'queued':
      return 20;
    case 'running':
      return 70;
    case 'succeeded':
      return 100;
    case 'failed':
    case 'cancelled':
      return 0;
    default:
      return 0;
  }
};

export const canCancelFineTuningJob = (job: FineTuningJob): boolean => {
  return job.status === 'validating_files' || job.status === 'queued' || job.status === 'running';
};

export const isFineTuningJobCompleted = (job: FineTuningJob): boolean => {
  return job.status === 'succeeded' || job.status === 'failed' || job.status === 'cancelled';
};

export const isFineTuningJobRunning = (job: FineTuningJob): boolean => {
  return job.status === 'running';
};

export const formatHyperparameters = (
  hyperparameters?: FineTuningHyperparameters | null
): string => {
  if (!hyperparameters) return 'Default';

  const params = [] as string[];
  if (hyperparameters.n_epochs) params.push(`Epochs: ${hyperparameters.n_epochs}`);
  if (hyperparameters.batch_size) params.push(`Batch: ${hyperparameters.batch_size}`);
  if (hyperparameters.learning_rate_multiplier) params.push(`LR: ${hyperparameters.learning_rate_multiplier}`);

  return params.length > 0 ? params.join(', ') : 'Default';
};

export const formatCreatedAt = (timestamp: number): string => {
  return new Date(timestamp * 1000).toLocaleString();
};

export const formatJobDuration = (job: FineTuningJob): string => {
  if (!job.finished_at || !job.created_at) {
    if (job.status === 'running') {
      const now = Math.floor(Date.now() / 1000);
      const duration = now - job.created_at;
      return formatDuration(duration);
    }
    return '-';
  }

  const duration = (job.finished_at ?? job.created_at) - job.created_at;
  return formatDuration(duration);
};

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
};

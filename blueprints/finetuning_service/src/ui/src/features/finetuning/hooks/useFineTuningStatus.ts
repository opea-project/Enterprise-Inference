import { useFineTuningJob } from './useFineTuningQueries';
import type { FineTuningJob, FineTuningJobStatus } from '../types';
import { calculateJobProgress } from '../utils/jobProgress';

const activeStatuses: FineTuningJobStatus[] = ['validating_files', 'queued', 'running'];
const completedStatuses: FineTuningJobStatus[] = ['succeeded', 'failed', 'cancelled'];

export function useJobStatusMonitor(jobId: string) {
  const { data: job } = useFineTuningJob(jobId);

  const status = job?.status;
  const isActive = status ? activeStatuses.includes(status) : false;
  const isCompleted = status ? completedStatuses.includes(status) : false;
  const isSuccessful = status === 'succeeded';
  const isFailed = status === 'failed';
  const isCancelled = status === 'cancelled';

  return {
    job,
    status,
    isActive,
    isCompleted,
    isSuccessful,
    isFailed,
    isCancelled,
    progress: calculateJobProgress(job as FineTuningJob | undefined),
  };
}

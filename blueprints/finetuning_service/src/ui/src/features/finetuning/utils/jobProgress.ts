import type { FineTuningJob } from '../types';

export function calculateJobProgress(job: FineTuningJob | undefined): number {
  if (!job) return 0;

  switch (job.status) {
    case 'validating_files':
      return 10;
    case 'queued':
      return 20;
    case 'running':
      if (job.trained_tokens && job.training_file) {
        return Math.min(80, 30 + (job.trained_tokens / 1000) * 0.1);
      }
      return 50;
    case 'succeeded':
      return 100;
    case 'failed':
    case 'cancelled':
      return 0;
    default:
      return 0;
  }
}

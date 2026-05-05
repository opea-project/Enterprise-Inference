import type {
  FineTuningJob,
  FineTuningJobStatus,
  FineTuningHyperparameters,
} from '@core/types';

export type {
  FineTuningJob,
  FineTuningJobStatus,
  FineTuningHyperparameters,
};

export type Hyperparameters = FineTuningHyperparameters;

export interface CreateFineTuningJobRequest {
  model: string;
  training_file: string;
  validation_file?: string | null;
  hyperparameters?: Hyperparameters | null;
  suffix?: string | null;
  resource_type?: string | null;
}

export interface FineTuningJobEvent {
  id: string;
  object: string;
  created_at: number;
  level: 'info' | 'warn' | 'error';
  message: string;
  data?: unknown;
  type?: string;
}

export interface ListFineTuningJobsResponse {
  object: string;
  data: FineTuningJob[];
  has_more: boolean;
}

export interface ListJobEventsResponse {
  object: string;
  data: FineTuningJobEvent[];
}

export interface FineTuningApiResponse<T = unknown> {
  data: T;
  message?: string;
  success: boolean;
}

export interface FineTuningJobDisplay extends FineTuningJob {
  key?: string;
  displayName: string;
  displayStatus: string;
  displayProgress: number;
  displayModel: string;
  displayDataset: string;
}

export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface ListModelsResponse {
  object: string;
  data: Model[];
}

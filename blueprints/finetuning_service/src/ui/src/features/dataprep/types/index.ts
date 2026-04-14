// Data Preparation Types based on OpenAPI specification

// Data Preparation Status Enum
export enum DataPrepStatus {
  PROCESSING = 'PROCESSING',
  SUCCESS = 'SUCCESS',
  FAILURE = 'FAILURE'
}

export interface PrepareDataRequest {
  file_ids: string[];
}

export interface PrepareDataResponse {
  submitted_job_ids: string[];
}

export interface DataPrepResult {
  aggregated_file_id: string;
  total_qa_pairs: number;
  successful_files: number;
  failed_files: number;
  status: string;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  result?: DataPrepResult;
  error?: string | null;
}

export interface JobWithStatus {
  job_id: string;
  user_id: string;
  file_id: string;
  submitted_at: string;
  status: string;
  result?: DataPrepResult;
  error?: string | null;
  metadata?: Record<string, unknown>;
}

export interface JobListResponse {
  user_id: string;
  total_jobs: number;
  jobs: JobWithStatus[];
}

export interface DataPrepApiError {
  message: string;
  type: string;
  param?: string | null;
  code?: string | null;
}

export interface DataPrepApiResponse<T> {
  data?: T;
  error?: DataPrepApiError;
}

// Common job statuses
export type JobStatus =
  | DataPrepStatus.PROCESSING
  | DataPrepStatus.SUCCESS
  | DataPrepStatus.FAILURE;

// UI specific types
export interface DataPrepJob extends JobWithStatus {
  progress?: number;
  duration?: number;
  created_at?: string;
  updated_at?: string;
}

export interface DataPrepFormData {
  selectedFileIds: string[];
  description?: string;
}
import { config } from '@core/config/appConfig';
import { nextAuthTokenStorage } from '../../auth/api/client';
import type {
  PrepareDataRequest,
  PrepareDataResponse,
  JobStatusResponse,
  JobListResponse,
  DataPrepApiError,
} from '../types';
import { DataPrepStatus } from '../types';

export class DataPrepApiServiceError extends Error {
  constructor(
    message: string,
    public type: string,
    public code?: string | null,
    public param?: string | null,
    public details?: unknown
  ) {
    super(message);
    this.name = 'DataPrepApiServiceError';
  }
}

async function dataPrepApiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const fullUrl = `${config.endpoints?.dataprep}${endpoint}`;

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Prefer JWT token from NextAuth, fallback to legacy token or API key
    const token = await nextAuthTokenStorage.get();
    if(token){
        headers.Authorization = `Bearer ${token}`;
    }

    if (options.headers) {
      const existingHeaders = new Headers(options.headers);
      existingHeaders.forEach((value, key) => {
        headers[key] = value;
      });
    }

    const response = await fetch(fullUrl, {
      ...options,
      headers,
    });

    const contentType = response.headers.get('content-type');

    if (!response.ok) {
      if (contentType?.includes('application/json')) {
        const errorData = await response.json().catch(() => ({}));
        const error = (errorData as { error?: DataPrepApiError }).error;
        throw new DataPrepApiServiceError(
          error?.message || `HTTP ${response.status}: ${response.statusText}`,
          error?.type || 'api_error',
          error?.code,
          error?.param,
          errorData
        );
      }

      throw new DataPrepApiServiceError(
        `HTTP ${response.status}: ${response.statusText}`,
        'http_error',
        String(response.status)
      );
    }

    if (contentType?.includes('application/json')) {
      const data = await response.json();
      return data as T;
    }

    const text = await response.text();
    return text as T;
  } catch (error) {
    if (error instanceof DataPrepApiServiceError) {
      throw error;
    }

    throw new DataPrepApiServiceError(
      error instanceof Error ? error.message : 'Unknown error occurred',
      'network_error',
      'NETWORK_ERROR',
      null,
      error
    );
  }
}

export const dataPrepApi = {
  /**
   * Submit data preparation jobs for multiple files
   * @param fileIds Array of file IDs to process
   * @returns Promise with submitted job IDs
   */
  async prepareData(fileIds: string[]): Promise<PrepareDataResponse> {
    const request: PrepareDataRequest = {
      file_ids: fileIds,
    };

    return dataPrepApiRequest<PrepareDataResponse>('/v1/dataprep', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get the status of a specific data preparation job
   * @param jobId The job ID to check
   * @returns Promise with job status and result
   */
  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return dataPrepApiRequest<JobStatusResponse>(`/v1/dataprep/status/${jobId}`);
  },

  /**
   * Get all data preparation jobs for the authenticated user
   * @returns Promise with list of all user's jobs
   */
  async getAllJobs(): Promise<JobListResponse> {
    return dataPrepApiRequest<JobListResponse>('/v1/dataprep/jobs');
  },

  /**
   * Submit multiple files for data preparation
   * @param fileIds Array of file IDs to process
   * @returns Promise with array of submitted job IDs
   */
  async prepareMultipleFiles(fileIds: string[]): Promise<string[]> {
    const response = await this.prepareData(fileIds);
    return response.submitted_job_ids;
  },

  /**
   * Get status for multiple jobs
   * @param jobIds Array of job IDs to check
   * @returns Promise with array of job statuses
   */
  async getMultipleJobStatuses(jobIds: string[]): Promise<JobStatusResponse[]> {
    const statusPromises = jobIds.map((jobId) => this.getJobStatus(jobId));
    return Promise.all(statusPromises);
  },

  /**
   * Poll job status until completion or failure
   * @param jobId The job ID to monitor
   * @param onUpdate Optional callback for status updates
   * @param pollInterval Polling interval in milliseconds (default: 2000)
   * @returns Promise that resolves when job is complete
   */
  async pollJobStatus(
    jobId: string,
    onUpdate?: (status: JobStatusResponse) => void,
    pollInterval: number = 2000
  ): Promise<JobStatusResponse> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getJobStatus(jobId);

          if (onUpdate) {
            onUpdate(status);
          }

          if (status.status === DataPrepStatus.SUCCESS || status.status === DataPrepStatus.FAILURE) {
            resolve(status);
            return;
          }

          setTimeout(poll, pollInterval);
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  },
};

export const {
  prepareData,
  getJobStatus,
  getAllJobs,
  prepareMultipleFiles,
  getMultipleJobStatuses,
  pollJobStatus,
} = dataPrepApi;
import { config } from '@core/config/appConfig';
import { nextAuthTokenStorage } from '../../auth/api/client';
import type {
  FineTuningJob,
  ListFineTuningJobsResponse,
  ListJobEventsResponse,
  CreateFineTuningJobRequest,
  ListModelsResponse,
} from '../types';

const API_BASE_URL = config.endpoints.fineTuning;
const API_TIMEOUT = config.endpoints.timeout;

const DEFAULT_HEADERS = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
  'Cache-Control': 'no-cache',
};

export class FineTuningApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'FineTuningApiError';
  }
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(new Error(`Request timeout after ${API_TIMEOUT}ms`));
  }, API_TIMEOUT);

  const token = await nextAuthTokenStorage.get();
  const headers: HeadersInit = { ...DEFAULT_HEADERS };

  // Merge with any existing headers
  if (options.headers) {
    Object.assign(headers, options.headers);
  }

  // Add Authorization header if token exists
  if (token) {
    (headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }

  const fullUrl = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetch(fullUrl, {
      ...options,
      signal: controller.signal,
      headers,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));

      // Handle nested error format: { error: { message, code, type } }
      const errorObj = (errorData as { error?: { message?: string; code?: string; type?: string } }).error;

      const errorMessage =
        errorObj?.message ||
        (errorData as { detail?: string; message?: string }).detail ||
        (errorData as { message?: string }).message ||
        `HTTP ${response.status}: ${response.statusText}`;

      const errorCode =
        errorObj?.code ||
        (errorData as { code?: string }).code ||
        'HTTP_ERROR';

      throw new FineTuningApiError(
        errorMessage,
        errorCode,
        errorData
      );
    }

    const data = await response.json();

    return data as T;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof FineTuningApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === 'AbortError') {
      const timeoutMessage = error.cause instanceof Error
        ? error.cause.message
        : `Request timeout after ${API_TIMEOUT}ms`;
      throw new FineTuningApiError(timeoutMessage, 'TIMEOUT', error);
    }

    throw new FineTuningApiError(
      error instanceof Error ? error.message : 'Unknown error occurred',
      'NETWORK_ERROR',
      error
    );
  }
}

export const fineTuningApi = {
  async createFineTuningJob(request: CreateFineTuningJobRequest): Promise<FineTuningJob> {
    return apiRequest<FineTuningJob>('/v1/fine_tuning/jobs', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async listFineTuningJobs(params?: { limit?: number; after?: string }): Promise<ListFineTuningJobsResponse> {
    const queryParams = new URLSearchParams();

    if (params?.limit) {
      queryParams.append('limit', params.limit.toString());
    }

    if (params?.after) {
      queryParams.append('after', params.after);
    }

    const endpoint = queryParams.toString()
      ? `/v1/fine_tuning/jobs?${queryParams.toString()}`
      : '/v1/fine_tuning/jobs';

    return apiRequest<ListFineTuningJobsResponse>(endpoint);
  },

  async getFineTuningJob(jobId: string): Promise<FineTuningJob> {
    return apiRequest<FineTuningJob>(`/v1/fine_tuning/jobs/${jobId}`);
  },

  async cancelFineTuningJob(jobId: string): Promise<FineTuningJob> {
    return apiRequest<FineTuningJob>(`/v1/fine_tuning/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  },

  async listJobEvents(jobId: string, params?: { limit?: number }): Promise<ListJobEventsResponse> {
    const queryParams = new URLSearchParams();

    if (params?.limit) {
      queryParams.append('limit', params.limit.toString());
    }

    const endpoint = queryParams.toString()
      ? `/v1/fine_tuning/jobs/${jobId}/events?${queryParams.toString()}`
      : `/v1/fine_tuning/jobs/${jobId}/events`;

    return apiRequest<ListJobEventsResponse>(endpoint);
  },

  async listModels(): Promise<ListModelsResponse> {
    return apiRequest<ListModelsResponse>('/v1/models');
  },
};

export default fineTuningApi;

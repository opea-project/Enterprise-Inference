import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from '@tanstack/react-query';
import { dataPrepApi, DataPrepApiServiceError } from '../api/client';
import type {
  PrepareDataResponse,
  JobStatusResponse,
  JobListResponse,
} from '../types';
import { DataPrepStatus } from '../types';
import { queryKeys, invalidateQueries } from '@core/query/queryClient';

/**
 * A React hook for submitting data preparation jobs.
 *
 * This hook provides a mutation for submitting files for data preparation processing.
 * After successful submission, it invalidates the dataprep jobs list to refresh the UI.
 *
 * @param options - Optional TanStack Query mutation options
 * @returns A mutation object for preparing data
 *
 * @example
 * ```typescript
 * const prepareDataMutation = usePrepareData({
 *   onSuccess: (response) => {
 *     console.log('Jobs submitted:', response.submitted_job_ids);
 *   },
 *   onError: (error) => {
 *     console.error('Failed to prepare data:', error.message);
 *   }
 * });
 *
 * const handleSubmit = () => {
 *   prepareDataMutation.mutate(['file-123', 'file-456']);
 * };
 * ```
 */
export function usePrepareData(
  options?: UseMutationOptions<PrepareDataResponse, DataPrepApiServiceError, string[]>
) {
  return useMutation({
    mutationFn: (fileIds: string[]) => dataPrepApi.prepareData(fileIds),
    onSuccess: (...args) => {
      // Invalidate jobs list to show new jobs
      invalidateQueries.dataPrep.jobs.all();
      options?.onSuccess?.(...args);
    },
    ...options,
  });
}

/**
 * A React hook for fetching the status of a specific data preparation job.
 *
 * This hook provides a query for retrieving job status, progress, and results.
 * The query is automatically enabled when a valid jobId is provided and caches
 * data for 30 seconds to provide near real-time updates.
 *
 * @param jobId - The unique identifier of the job to check
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with job status data, loading state, and error information
 *
 * @example
 * ```typescript
 * const { data: jobStatus, isLoading } = useJobStatus('job-123');
 *
 * // With polling for real-time updates
 * const { data: jobStatus } = useJobStatus(jobId, {
 *   refetchInterval: 2000, // Poll every 2 seconds
 *   enabled: jobId && ![DataPrepStatus.SUCCESS, DataPrepStatus.FAILED].includes(jobStatus?.status)
 * });
 * ```
 */
export function useJobStatus(
  jobId: string,
  options?: Omit<UseQueryOptions<JobStatusResponse, DataPrepApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.dataPrep.jobs.detail(jobId),
    queryFn: () => dataPrepApi.getJobStatus(jobId),
    enabled: !!jobId,
    staleTime: 30 * 1000, // 30 seconds for near real-time updates
    refetchInterval: (query) => {
      // Stop polling when job is complete or failed
      const data = query.state.data;
      if (data && [DataPrepStatus.SUCCESS, DataPrepStatus.FAILURE].includes(data.status as DataPrepStatus)) {
        return false;
      }
      return 5000; // Poll every 5 seconds for active jobs
    },
    ...options,
  });
}

/**
 * A React hook for fetching all data preparation jobs for the authenticated user.
 *
 * This hook provides a query for retrieving all user's dataprep jobs with their
 * current status, metadata, and results. The data is cached for 1 minute.
 *
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with jobs list data, loading state, and error information
 *
 * @example
 * ```typescript
 * const { data: jobsList, isLoading } = useDataPrepJobs();
 *
 * // With custom options
 * const { data: jobsList, refetch } = useDataPrepJobs({
 *   onSuccess: (data) => {
 *     console.log(`Found ${data.total_jobs} jobs`);
 *   }
 * });
 * ```
 */
export function useDataPrepJobs(
  options?: Omit<UseQueryOptions<JobListResponse, DataPrepApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.dataPrep.jobs.lists(),
    queryFn: () => dataPrepApi.getAllJobs(),
    staleTime: 0, // Always consider data stale to refetch when invalidated
    ...options,
  });
}

/**
 * A React hook for fetching the statuses of multiple jobs at once.
 *
 * This hook provides a query for retrieving status information for multiple jobs
 * in a single operation. Useful for dashboard views or batch status checking.
 *
 * @param jobIds - Array of job IDs to check
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with array of job statuses, loading state, and error information
 *
 * @example
 * ```typescript
 * const jobIds = ['job-1', 'job-2', 'job-3'];
 * const { data: jobStatuses, isLoading } = useMultipleJobStatuses(jobIds);
 *
 * // With conditional polling
 * const { data: jobStatuses } = useMultipleJobStatuses(activeJobIds, {
 *   enabled: activeJobIds.length > 0,
 *   refetchInterval: 10000 // Poll every 10 seconds
 * });
 * ```
 */
export function useMultipleJobStatuses(
  jobIds: string[],
  options?: Omit<UseQueryOptions<JobStatusResponse[], DataPrepApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: [...queryKeys.dataPrep.jobs.all(), 'multiple-status', jobIds],
    queryFn: () => dataPrepApi.getMultipleJobStatuses(jobIds),
    enabled: jobIds.length > 0,
    staleTime: 30 * 1000,
    ...options,
  });
}

/**
 * A React hook that provides utilities for managing dataprep operations.
 *
 * This hook returns utility functions for common dataprep operations like
 * refreshing job lists, checking if jobs are active, and formatting job data.
 *
 * @returns Object with utility functions and state helpers
 *
 * @example
 * ```typescript
 * const {
 *   refreshJobs,
 *   isJobActive,
 *   getActiveJobs,
 *   formatJobDuration
 * } = useDataPrepUtilities();
 *
 * // Refresh jobs list
 * const handleRefresh = () => refreshJobs();
 *
 * // Check if job is still processing
 * const isProcessing = isJobActive(jobStatus);
 *
 * // Get all active jobs
 * const activeJobs = getActiveJobs(allJobs);
 * ```
 */
export function useDataPrepUtilities() {
  const queryClient = useQueryClient();

  const refreshJobs = () => {
    return invalidateQueries.dataPrep.jobs.all();
  };

  const refreshJobStatus = (jobId: string) => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.dataPrep.jobs.detail(jobId)
    });
  };

  const isJobActive = (status?: string) => {
    if (!status) return false;
    return status === DataPrepStatus.PROCESSING;
  };

  const isJobComplete = (status?: string) => {
    if (!status) return false;
    return status === DataPrepStatus.SUCCESS;
  };

  const getActiveJobs = (jobs?: JobListResponse['jobs']) => {
    if (!jobs) return [];
    return jobs.filter(job => isJobActive(job.status));
  };

  const getCompletedJobs = (jobs?: JobListResponse['jobs']) => {
    if (!jobs) return [];
    return jobs.filter(job => isJobComplete(job.status));
  };

  const formatJobDuration = (submittedAt: string, completedAt?: string) => {
    const start = new Date(submittedAt);
    const end = completedAt ? new Date(completedAt) : new Date();
    const durationMs = end.getTime() - start.getTime();

    if (durationMs < 60000) {
      return `${Math.floor(durationMs / 1000)}s`;
    }

    const minutes = Math.floor(durationMs / 60000);
    const seconds = Math.floor((durationMs % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  const getJobStatusColor = (status: string) => {
    switch (status) {
      case DataPrepStatus.SUCCESS:
        return 'success';
      case DataPrepStatus.FAILURE:
        return 'error';
      case DataPrepStatus.PROCESSING:
        return 'processing';
      default:
        return 'default';
    }
  };


  return {
    refreshJobs,
    refreshJobStatus,
    isJobActive,
    isJobComplete,
    getActiveJobs,
    getCompletedJobs,
    formatJobDuration,
    getJobStatusColor,
  };
}
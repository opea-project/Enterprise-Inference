import {
  useMutation,
  UseMutationOptions,
} from '@tanstack/react-query';
import { dataPrepApi, DataPrepApiServiceError } from '../api/client';
import type {
  PrepareDataResponse,
  JobStatusResponse,
} from '../types';
import { invalidateQueries } from '@core/query/queryClient';

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
 * const prepareDataMutation = usePrepareDataMutation({
 *   onSuccess: (response) => {
 *     console.log('Jobs submitted:', response.submitted_job_ids);
 *     // Show success notification
 *   },
 *   onError: (error) => {
 *     console.error('Failed to prepare data:', error.message);
 *     // Show error notification
 *   }
 * });
 *
 * const handleSubmit = (fileIds: string[]) => {
 *   prepareDataMutation.mutate(fileIds);
 * };
 * ```
 */
export function usePrepareDataMutation(
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
 * A React hook for submitting multiple files for data preparation.
 *
 * This hook is similar to `usePrepareDataMutation` but specifically designed
 * for batch operations with multiple files. It returns the job IDs directly.
 *
 * @param options - Optional TanStack Query mutation options
 * @returns A mutation object for preparing multiple files
 *
 * @example
 * ```typescript
 * const prepareMultipleMutation = usePrepareMultipleFilesMutation({
 *   onSuccess: (jobIds) => {
 *     console.log(`Submitted ${jobIds.length} jobs`);
 *     // Navigate to jobs overview or show progress
 *   }
 * });
 *
 * const handleBatchSubmit = (selectedFileIds: string[]) => {
 *   prepareMultipleMutation.mutate(selectedFileIds);
 * };
 * ```
 */
export function usePrepareMultipleFilesMutation(
  options?: UseMutationOptions<string[], DataPrepApiServiceError, string[]>
) {
  return useMutation({
    mutationFn: (fileIds: string[]) => dataPrepApi.prepareMultipleFiles(fileIds),
    onSuccess: (...args) => {
      // Invalidate jobs list to show new jobs
      invalidateQueries.dataPrep.jobs.all();
      options?.onSuccess?.(...args);
    },
    ...options,
  });
}

/**
 * A React hook that provides utilities for dataprep mutations.
 *
 * This hook returns helper functions for common mutation scenarios
 * and state management around dataprep operations.
 *
 * @returns Object with mutation helper functions
 *
 * @example
 * ```typescript
 * const {
 *   prepareWithNotification,
 *   prepareAndPoll,
 *   cancelPendingJobs
 * } = useDataPrepMutationUtilities();
 *
 * // Prepare data with built-in notifications
 * const handlePrepare = (fileIds: string[]) => {
 *   prepareWithNotification(fileIds, {
 *     successMessage: 'Data preparation started!',
 *     errorMessage: 'Failed to start data preparation'
 *   });
 * };
 * ```
 */
export function useDataPrepMutationUtilities() {
  const prepareDataMutation = usePrepareDataMutation();

  const prepareWithNotification = (
    fileIds: string[],
    options?: {
      successMessage?: string;
      errorMessage?: string;
      onSuccess?: (response: PrepareDataResponse) => void;
      onError?: (error: DataPrepApiServiceError) => void;
    }
  ) => {
    return prepareDataMutation.mutate(fileIds, {
      onSuccess: (response) => {
        // Here you would typically show a success notification
        options?.onSuccess?.(response);
      },
      onError: (error) => {
        // Here you would typically show an error notification
        options?.onError?.(error);
      },
    });
  };

  const prepareAndPoll = async (
    fileIds: string[],
    onUpdate?: (jobId: string, status: JobStatusResponse) => void
  ) => {
    try {
      const response = await dataPrepApi.prepareData(fileIds);

      // Start polling for each job
      const pollPromises = response.submitted_job_ids.map(jobId =>
        dataPrepApi.pollJobStatus(jobId, (status) => {
          onUpdate?.(jobId, status);
        })
      );

      return Promise.all(pollPromises);
    } catch (error) {
      throw error;
    }
  };

  return {
    prepareDataMutation,
    prepareWithNotification,
    prepareAndPoll,
    isLoading: prepareDataMutation.isPending,
    error: prepareDataMutation.error,
    reset: prepareDataMutation.reset,
  };
}
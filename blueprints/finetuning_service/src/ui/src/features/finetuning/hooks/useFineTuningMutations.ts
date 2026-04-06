import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from '@tanstack/react-query';
import { fineTuningApi, FineTuningApiError } from '../api/client';
import type {
  FineTuningJob,
  CreateFineTuningJobRequest,
  ListFineTuningJobsResponse,
} from '../types';
import { queryKeys, invalidateQueries, handleQueryError } from '@core/query/queryClient';

export function useCreateFineTuningJob(
  options?: UseMutationOptions<FineTuningJob, FineTuningApiError, CreateFineTuningJobRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateFineTuningJobRequest) => fineTuningApi.createFineTuningJob(request),
    onSuccess: (data) => {
      invalidateQueries.fineTuning.jobs.lists();
      queryClient.setQueryData(queryKeys.fineTuning.jobs.detail(data.id), data);
      queryClient.setQueriesData(
        { queryKey: queryKeys.fineTuning.jobs.lists() },
        (oldData: ListFineTuningJobsResponse | undefined) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            data: [data, ...oldData.data],
            first_id: data.id,
          };
        }
      );
    },
    onError: (error) => {
      handleQueryError(error);
    },
    ...options,
  });
}

export function useCancelFineTuningJob(
  options?: UseMutationOptions<FineTuningJob, FineTuningApiError, string, { previousJob: unknown }>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => fineTuningApi.cancelFineTuningJob(jobId),
    onMutate: async (jobId): Promise<{ previousJob: unknown }> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.fineTuning.jobs.detail(jobId) });
      const previousJob = queryClient.getQueryData(queryKeys.fineTuning.jobs.detail(jobId));
      queryClient.setQueryData(
        queryKeys.fineTuning.jobs.detail(jobId),
        (old: FineTuningJob | undefined) => (old ? { ...old, status: 'cancelled' } : old)
      );
      return { previousJob };
    },
    onError: (error, jobId, context) => {
      if (context?.previousJob) {
        queryClient.setQueryData(queryKeys.fineTuning.jobs.detail(jobId), context.previousJob);
      }
      handleQueryError(error);
    },
    onSettled: (_data, _error, jobId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.fineTuning.jobs.detail(jobId) });
      invalidateQueries.fineTuning.jobs.lists();
    },
    ...options,
  });
}

import {
  useQuery,
  useInfiniteQuery,
  UseQueryOptions,
  UseInfiniteQueryOptions,
} from '@tanstack/react-query';
import { fineTuningApi, FineTuningApiError } from '../api/client';
import type {
  FineTuningJob,
  ListFineTuningJobsResponse,
  ListJobEventsResponse,
  FineTuningJobStatus,
  ListModelsResponse,
} from '../types';
import { queryKeys } from '@core/query/queryClient';

export function useFineTuningJobsList(
  params?: { limit?: number; after?: string },
  options?: Omit<UseQueryOptions<ListFineTuningJobsResponse, FineTuningApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.fineTuning.jobs.list(params),
    queryFn: () => fineTuningApi.listFineTuningJobs(params),
    staleTime: 30 * 1000,
    // refetchInterval: (query) => {      //auto refetch if there are any active jobs
    //   const data = query.state.data;
    //   const hasActiveJobs = data?.data?.some((job: FineTuningJob) =>
    //     ['validating_files', 'queued', 'running'].includes(job.status)
    //   );
    //   return hasActiveJobs ? 10000 : false;
    // },
    ...options,
  });
}

export function useFineTuningJobsInfinite(
  params?: { limit?: number },
  options?: Omit<
    UseInfiniteQueryOptions<
      ListFineTuningJobsResponse,
      FineTuningApiError
    >,
    'queryKey' | 'queryFn' | 'getNextPageParam' | 'initialPageParam'
  >
) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.fineTuning.jobs.lists(), 'infinite', params],
    queryFn: ({ pageParam }) =>
      fineTuningApi.listFineTuningJobs({
        ...params,
        after: pageParam as string | undefined,
      }),
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => {
      return lastPage.has_more && lastPage.data.length > 0
        ? lastPage.data[lastPage.data.length - 1].id
        : undefined;
    },
    staleTime: 30 * 1000,
    ...options,
  });
}

export function useFineTuningJob(
  jobId: string,
  options?: Omit<UseQueryOptions<FineTuningJob, FineTuningApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.fineTuning.jobs.detail(jobId),
    queryFn: () => fineTuningApi.getFineTuningJob(jobId),
    enabled: !!jobId,
    staleTime: 10 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const activeStatuses: FineTuningJobStatus[] = ['validating_files', 'queued', 'running'];
      return activeStatuses.includes(data.status) ? 20*1000 : false; //every 20 seconds if job is active
    },
    ...options,
  });
}

export function useJobEvents(
  jobId: string,
  params?: { limit?: number },
  options?: Omit<UseQueryOptions<ListJobEventsResponse, FineTuningApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.fineTuning.jobs.events(jobId, params),
    queryFn: () => fineTuningApi.listJobEvents(jobId, params),
    enabled: !!jobId,
    staleTime: 5 * 1000,
    ...options,
  });
}

export function useModels(
  options?: Omit<UseQueryOptions<ListModelsResponse, FineTuningApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.fineTuning.models(),
    queryFn: () => fineTuningApi.listModels(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

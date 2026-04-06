import { QueryClient } from '@tanstack/react-query';
import type { ListFilesParams, FilePurpose } from '@features/files/types';

const getErrorCode = (error: unknown): string | undefined => {
  if (typeof error !== 'object' || error === null) {
    return undefined;
  }

  const code = (error as { code?: unknown }).code;
  return typeof code === 'string' ? code : undefined;
};

const getErrorStatus = (error: unknown): number | undefined => {
  if (typeof error !== 'object' || error === null) {
    return undefined;
  }

  const details = (error as { details?: unknown }).details;
  if (typeof details !== 'object' || details === null) {
    return undefined;
  }

  const status = (details as { status?: unknown }).status;
  if (typeof status === 'number') {
    return status;
  }

  if (typeof status === 'string') {
    const parsed = Number(status);
    return Number.isNaN(parsed) ? undefined : parsed;
  }

  return undefined;
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: (failureCount, error) => {
        const code = getErrorCode(error);
        const status = getErrorStatus(error);

        if (code === 'HTTP_ERROR' && status && status >= 400 && status < 500) {
          if (status === 408 || status === 429) {
            return failureCount < 2;
          }
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnMount: true,
      refetchOnReconnect: 'always',
      throwOnError: false,
      // Expose fetching state transitions to subscribers that rely on refetch indicators
      notifyOnChangeProps: ['data', 'error', 'isLoading', 'isFetching'],
    },
    mutations: {
      retry: (failureCount, error) => {
        const code = getErrorCode(error);
        const status = getErrorStatus(error);

        if (code === 'HTTP_ERROR' && status && status >= 400 && status < 500) {
          return false;
        }
        return failureCount < 2;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
      onError: () => {
      },
    },
  },
});

export const queryKeys = {
  user: {
    all: ['user'] as const,
    current: () => [...queryKeys.user.all, 'current'] as const,
    profile: () => [...queryKeys.user.all, 'profile'] as const,
  },
  files: {
    all: ['files'] as const,
    lists: () => [...queryKeys.files.all, 'list'] as const,
    list: (params?: ListFilesParams) => [...queryKeys.files.lists(), params] as const,
    detail: (id: string) => [...queryKeys.files.all, 'detail', id] as const,
    content: (id: string) => [...queryKeys.files.all, 'content', id] as const,
    byPurpose: (purpose: FilePurpose) => [...queryKeys.files.all, 'purpose', purpose] as const,
  },
  fineTuning: {
    all: ['fineTuning'] as const,
    models: () => [...queryKeys.fineTuning.all, 'models'] as const,
    jobs: {
      all: () => [...queryKeys.fineTuning.all, 'jobs'] as const,
      lists: () => [...queryKeys.fineTuning.jobs.all(), 'list'] as const,
      list: (params?: { limit?: number; after?: string }) => [...queryKeys.fineTuning.jobs.lists(), params] as const,
      detail: (id: string) => [...queryKeys.fineTuning.jobs.all(), 'detail', id] as const,
      events: (id: string, params?: { limit?: number }) => [...queryKeys.fineTuning.jobs.detail(id), 'events', params] as const,
    },
  },
  dataPrep: {
    all: ['dataPrep'] as const,
    jobs: {
      all: () => [...queryKeys.dataPrep.all, 'jobs'] as const,
      lists: () => [...queryKeys.dataPrep.jobs.all(), 'list'] as const,
      detail: (id: string) => [...queryKeys.dataPrep.jobs.all(), 'detail', id] as const,
    },
  },
} as const;

export const invalidateQueries = {
  user: () => queryClient.invalidateQueries({ queryKey: queryKeys.user.all }),
  files: {
    all: () => queryClient.invalidateQueries({ queryKey: queryKeys.files.all }),
    lists: () => queryClient.invalidateQueries({ queryKey: queryKeys.files.lists() }),
    byPurpose: (purpose: FilePurpose) => queryClient.invalidateQueries({ queryKey: queryKeys.files.byPurpose(purpose) }),
  },
  fineTuning: {
    all: () => queryClient.invalidateQueries({ queryKey: queryKeys.fineTuning.all }),
    models: () => queryClient.invalidateQueries({ queryKey: queryKeys.fineTuning.models() }),
    jobs: {
      all: () => queryClient.invalidateQueries({ queryKey: queryKeys.fineTuning.jobs.all() }),
      lists: () => queryClient.invalidateQueries({ queryKey: queryKeys.fineTuning.jobs.lists() }),
    },
  },
  dataPrep: {
    all: () => queryClient.invalidateQueries({ queryKey: queryKeys.dataPrep.all }),
    jobs: {
      all: () => queryClient.invalidateQueries({ queryKey: queryKeys.dataPrep.jobs.all() }),
      lists: () => queryClient.invalidateQueries({ queryKey: queryKeys.dataPrep.jobs.lists() }),
    },
  },
};

export class QueryErrorBoundary extends Error {
  constructor(message: string, public originalError?: unknown) {
    super(message);
    this.name = 'QueryErrorBoundary';
  }
}

export const handleQueryError = (error: unknown) => {
  return error;
};

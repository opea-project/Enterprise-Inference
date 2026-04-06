import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
  QueryKey,
} from '@tanstack/react-query';
import { filesApi, FilesApiServiceError } from '../api/client';
import type {
  FileObject,
  FilePurpose,
  FileExpiresAfter,
  ListFilesResponse,
  DeleteFileResponse,
} from '../types';
import { queryKeys, invalidateQueries, handleQueryError } from '@core/query/queryClient';

/**
 * A React hook for uploading a single file to the files API.
 *
 * This hook provides a mutation for uploading files with automatic cache management.
 * On successful upload, it updates the query cache with the new file data and invalidates
 * relevant queries to ensure UI consistency.
 *
 * @param options - Optional TanStack Query mutation options to customize behavior
 * @returns A mutation object with methods and state for file upload
 *
 * @example
 * ```typescript
 * const uploadFile = useUploadFile({
 *   onSuccess: (data) => {
 *     console.log('File uploaded:', data.filename);
 *   }
 * });
 *
 * const handleUpload = (file: File) => {
 *   uploadFile.mutate({
 *     file,
 *     purpose: 'fine-tune',
 *     expiresAfter: { anchor: 'created_at', seconds: 86400 }
 *   });
 * };
 * ```
 */
export function useUploadFile(
  options?: UseMutationOptions<
    FileObject,
    FilesApiServiceError,
    { file: File; purpose: FilePurpose; expiresAfter?: FileExpiresAfter }
  >
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, purpose, expiresAfter }) => filesApi.uploadFile(file, purpose, expiresAfter),
    onSuccess: (data, variables) => {
      invalidateQueries.files.lists();
      invalidateQueries.files.byPurpose(variables.purpose);
      queryClient.setQueryData(queryKeys.files.detail(data.id), data);
      queryClient.setQueriesData(
        { queryKey: queryKeys.files.lists() },
        (oldData: ListFilesResponse | undefined) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            data: [data, ...oldData.data],
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

/**
 * A React hook for uploading multiple files simultaneously to the files API.
 *
 * This hook provides a mutation for batch file uploads with automatic cache management.
 * It efficiently handles multiple file uploads and updates the query cache for all
 * uploaded files while invalidating relevant queries.
 *
 * @param options - Optional TanStack Query mutation options to customize behavior
 * @returns A mutation object with methods and state for multiple file upload
 *
 * @example
 * ```typescript
 * const uploadMultipleFiles = useUploadMultipleFiles({
 *   onSuccess: (files) => {
 *     console.log(`${files.length} files uploaded successfully`);
 *   }
 * });
 *
 * const handleMultipleUpload = (fileList: FileList) => {
 *   const files = Array.from(fileList).map(file => ({
 *     file,
 *     purpose: 'fine-tune' as FilePurpose,
 *     expiresAfter: { anchor: 'created_at' as const, seconds: 86400 }
 *   }));
 *
 *   uploadMultipleFiles.mutate(files);
 * };
 * ```
 */
export function useUploadMultipleFiles(
  options?: UseMutationOptions<
    FileObject[],
    FilesApiServiceError,
    Array<{ file: File; purpose: FilePurpose; expiresAfter?: FileExpiresAfter }>
  >
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (files) => filesApi.uploadMultipleFiles(files),
    onSuccess: (data, variables) => {
      invalidateQueries.files.lists();
      const purposes = [...new Set(variables.map((file) => file.purpose))];
      purposes.forEach((purpose) => invalidateQueries.files.byPurpose(purpose));
      data.forEach((file) => {
        queryClient.setQueryData(queryKeys.files.detail(file.id), file);
      });
    },
    onError: (error) => {
      handleQueryError(error);
    },
    ...options,
  });
}

/**
 * A React hook for deleting a single file from the files API.
 *
 * This hook provides a mutation for file deletion with comprehensive cache cleanup.
 * On successful deletion, it removes all cached data related to the file including
 * file details, content, and updates file lists to maintain UI consistency.
 *
 * @param options - Optional TanStack Query mutation options to customize behavior
 * @returns A mutation object with methods and state for file deletion
 *
 * @example
 * ```typescript
 * const deleteFile = useDeleteFile({
 *   onSuccess: () => {
 *     message.success('File deleted successfully');
 *   },
 *   onError: (error) => {
 *     message.error(`Failed to delete file: ${error.message}`);
 *   }
 * });
 *
 * const handleDelete = (fileId: string) => {
 *   deleteFile.mutate(fileId);
 * };
 * ```
 */

type DeleteFileMutationContext = {
  previousListData: Array<[QueryKey, ListFilesResponse | undefined]>;
  previousPurposeData: Array<[QueryKey, FileObject[] | undefined]>;
  userContext?: unknown;
};

export function useDeleteFile(
  options?: UseMutationOptions<
    DeleteFileResponse,
    FilesApiServiceError,
    FileObject,
    DeleteFileMutationContext
  >
) {
  const queryClient = useQueryClient();

  return useMutation({
    ...options,
    mutationFn: (file: FileObject) => filesApi.deleteFile(file.id),
    onMutate: async (file) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.files.all });

      const previousListData = queryClient.getQueriesData<ListFilesResponse>({
        queryKey: queryKeys.files.lists(),
      });

      previousListData.forEach(([key, snapshot]) => {
        if (!snapshot) return;

        const filteredData = snapshot.data.filter((item) => item.id !== file.id);
        if (filteredData.length === snapshot.data.length) return;

        queryClient.setQueryData<ListFilesResponse>(key, {
          ...snapshot,
          data: filteredData,
          first_id: filteredData[0]?.id ?? null,
          last_id: filteredData[filteredData.length - 1]?.id ?? null,
        });
      });

      const previousPurposeData = file.purpose
        ? queryClient.getQueriesData<FileObject[]>({
            queryKey: queryKeys.files.byPurpose(file.purpose as FilePurpose),
          })
        : [];

      previousPurposeData.forEach(([key, snapshot]) => {
        if (!snapshot) return;

        const filteredPurposeData = snapshot.filter((item) => item.id !== file.id);
        if (filteredPurposeData.length === snapshot.length) return;

        queryClient.setQueryData<FileObject[]>(key, filteredPurposeData);
      });

      // Let React Query handle the user's onMutate separately
      const userContext = undefined;

      return {
        previousListData,
        previousPurposeData,
        userContext,
      } satisfies DeleteFileMutationContext;
    },
    onError: (error, file, context) => {
      if (context) {
        context.previousListData.forEach(([key, snapshot]) => {
          queryClient.setQueryData(key, snapshot);
        });
        context.previousPurposeData.forEach(([key, snapshot]) => {
          queryClient.setQueryData(key, snapshot);
        });
      }
      handleQueryError(error);
    },
    onSuccess: (_data, file) => {
      queryClient.removeQueries({ queryKey: queryKeys.files.detail(file.id) });
      queryClient.removeQueries({ queryKey: queryKeys.files.content(file.id) });
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.files.all,
        type: 'inactive',
      });
    },
  });
}

/**
 * A React hook for deleting multiple files simultaneously from the files API.
 *
 * This hook provides a mutation for batch file deletion with efficient cache management.
 * It removes all cached data for the specified files and updates file lists to reflect
 * the deletions. Ideal for bulk operations like clearing selected files.
 *
 * @param options - Optional TanStack Query mutation options to customize behavior
 * @returns A mutation object with methods and state for multiple file deletion
 *
 * @example
 * ```typescript
 * const deleteMultipleFiles = useDeleteMultipleFiles({
 *   onSuccess: (results, fileIds) => {
 *     message.success(`${fileIds.length} files deleted successfully`);
 *   }
 * });
 *
 * const handleBulkDelete = (selectedFileIds: string[]) => {
 *   if (selectedFileIds.length > 0) {
 *     deleteMultipleFiles.mutate(selectedFileIds);
 *   }
 * };
 * ```
 */
export function useDeleteMultipleFiles(
  options?: UseMutationOptions<DeleteFileResponse[], FilesApiServiceError, string[]>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fileIds: string[]) => filesApi.deleteMultipleFiles(fileIds),
    onSuccess: (_data, fileIds) => {
      fileIds.forEach((fileId) => {
        queryClient.removeQueries({ queryKey: queryKeys.files.detail(fileId) });
        queryClient.removeQueries({ queryKey: queryKeys.files.content(fileId) });
      });
      invalidateQueries.files.lists();
      queryClient.setQueriesData(
        { queryKey: queryKeys.files.lists() },
        (oldData: ListFilesResponse | undefined) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            data: oldData.data.filter((file) => !fileIds.includes(file.id)),
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

/**
 * A React hook for downloading files from the files API.
 *
 * This hook provides a mutation for file downloads with proper error handling.
 * It triggers the browser's download mechanism for the specified file, with an
 * optional custom filename. The download is handled client-side through the browser's
 * native download functionality.
 *
 * @param options - Optional TanStack Query mutation options to customize behavior
 * @returns A mutation object with methods and state for file download
 *
 * @example
 * ```typescript
 * const downloadFile = useDownloadFile({
 *   onSuccess: () => {
 *     message.success('Download started');
 *   },
 *   onError: (error) => {
 *     message.error(`Download failed: ${error.message}`);
 *   }
 * });
 *
 * const handleDownload = (fileId: string, customName?: string) => {
 *   downloadFile.mutate({
 *     fileId,
 *     filename: customName
 *   });
 * };
 * ```
 */
export function useDownloadFile(
  options?: UseMutationOptions<void, FilesApiServiceError, { fileId: string; filename?: string }>
) {
  return useMutation({
    mutationFn: ({ fileId, filename }) => filesApi.downloadFile(fileId, filename),
    onError: (error) => {
      handleQueryError(error);
    },
    ...options,
  });
}

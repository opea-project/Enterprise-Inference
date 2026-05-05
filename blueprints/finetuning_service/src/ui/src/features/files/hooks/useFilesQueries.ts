import {
  useQuery,
  UseQueryOptions,
} from '@tanstack/react-query';
import { filesApi, FilesApiServiceError } from '../api/client';
import type {
  FileObject,
  ListFilesParams,
  ListFilesResponse,
  FilePurpose,
} from '../types';
import { queryKeys } from '@core/query/queryClient';

/**
 * A React hook for fetching a paginated list of files from the files API.
 *
 * This hook provides a query for retrieving files with optional filtering and pagination.
 * It supports filtering by purpose, ordering, and pagination through the API parameters.
 * The data is cached for 2 minutes to improve performance.
 *
 * @param params - Optional parameters for filtering and pagination
 * @param params.after - Cursor for pagination (file ID to start after)
 * @param params.limit - Maximum number of files to return (default varies by API)
 * @param params.order - Sort order: 'asc' or 'desc'
 * @param params.purpose - Filter files by purpose (e.g., 'fine-tune', 'assistants')
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with file list data, loading state, and error information
 *
 * @example
 * ```typescript
 * // Basic usage - get all files
 * const { data: allFiles, isLoading } = useFilesList();
 *
 * // With filtering and pagination
 * const { data: fineTuneFiles } = useFilesList({
 *   purpose: 'fine-tune',
 *   limit: 20,
 *   order: 'desc'
 * });
 *
 * // With custom options
 * const { data: files } = useFilesList(
 *   { purpose: 'assistants' },
 *   { refetchOnWindowFocus: false }
 * );
 * ```
 */
export function useFilesList(
  params?: ListFilesParams,
  options?: Omit<UseQueryOptions<ListFilesResponse, FilesApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.files.list(params),
    queryFn: () => filesApi.listFiles(params),
    staleTime: 2 * 60 * 1000,
    ...options,
  });
}

/**
 * A React hook for fetching detailed information about a specific file.
 *
 * This hook provides a query for retrieving file metadata including filename, size,
 * creation date, purpose, and status. The query is automatically enabled when a valid
 * fileId is provided and caches data for 5 minutes.
 *
 * @param fileId - The unique identifier of the file to retrieve
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with file data, loading state, and error information
 *
 * @example
 * ```typescript
 * // Basic usage
 * const { data: file, isLoading, error } = useFile('file-123');
 *
 * // Conditional usage
 * const { data: file } = useFile(selectedFileId, {
 *   enabled: !!selectedFileId && isModalOpen
 * });
 *
 * // With error handling
 * const { data: file, error } = useFile(fileId, {
 *   onError: (error) => {
 *     console.error('Failed to load file:', error.message);
 *   }
 * });
 * ```
 */
export function useFile(
  fileId: string,
  options?: Omit<UseQueryOptions<FileObject, FilesApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.files.detail(fileId),
    queryFn: () => filesApi.retrieveFile(fileId),
    enabled: !!fileId,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

/**
 * A React hook for fetching the actual content/data of a file as a Blob.
 *
 * This hook provides a query for retrieving file content which can be used for
 * file preview, processing, or download preparation. The content is cached for
 * 10 minutes with a garbage collection time of 5 minutes to manage memory usage.
 *
 * @param fileId - The unique identifier of the file whose content to retrieve
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with file content as Blob, loading state, and error information
 *
 * @example
 * ```typescript
 * // Basic usage for file preview
 * const { data: fileBlob, isLoading } = useFileContent(fileId);
 *
 * // Convert blob to text for text files
 * const { data: fileBlob } = useFileContent(fileId);
 * useEffect(() => {
 *   if (fileBlob) {
 *     fileBlob.text().then(content => {
 *       setFileContent(content);
 *     });
 *   }
 * }, [fileBlob]);
 *
 * // Create object URL for file preview
 * const { data: fileBlob } = useFileContent(fileId);
 * const previewUrl = useMemo(() => {
 *   return fileBlob ? URL.createObjectURL(fileBlob) : null;
 * }, [fileBlob]);
 * ```
 */
export function useFileContent(
  fileId: string,
  options?: Omit<UseQueryOptions<Blob, FilesApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.files.content(fileId),
    queryFn: () => filesApi.retrieveFileContent(fileId),
    enabled: !!fileId,
    staleTime: 10 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    ...options,
  });
}

/**
 * A React hook for fetching files filtered by a specific purpose.
 *
 * This hook provides a query for retrieving all files that match a specific purpose
 * (e.g., 'fine-tune', 'assistants', 'batch'). This is useful for displaying files
 * in purpose-specific sections of the UI. The data is cached for 2 minutes.
 *
 * @param purpose - The file purpose to filter by
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with filtered file array, loading state, and error information
 *
 * @example
 * ```typescript
 * // Get all fine-tuning files
 * const { data: fineTuneFiles, isLoading } = useFilesByPurpose('fine-tune');
 *
 * // Get assistant files with custom options
 * const { data: assistantFiles } = useFilesByPurpose('assistants', {
 *   refetchInterval: 30000, // Refetch every 30 seconds
 *   onSuccess: (files) => {
 *     console.log(`Found ${files.length} assistant files`);
 *   }
 * });
 *
 * // Conditional loading based on selected tab
 * const { data: files } = useFilesByPurpose(selectedPurpose, {
 *   enabled: !!selectedPurpose
 * });
 * ```
 */
export function useFilesByPurpose(
  purpose: FilePurpose,
  options?: Omit<UseQueryOptions<FileObject[], FilesApiServiceError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.files.byPurpose(purpose),
    queryFn: () => filesApi.getFilesByPurpose(purpose),
    staleTime: 2 * 60 * 1000,
    ...options,
  });
}

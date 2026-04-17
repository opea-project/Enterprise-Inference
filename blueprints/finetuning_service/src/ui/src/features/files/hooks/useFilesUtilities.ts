
import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { filesApi, FilesApiServiceError } from '../api/client';
import type { FileObject } from '../types';
import { queryKeys } from '@core/query/queryClient';

/**
 * A React hook for getting just the filename of a file by its ID.
 *
 * This hook provides an efficient way to retrieve only the filename without needing
 * the full file object. It uses the existing file detail query but transforms the
 * result to return only the filename. This is useful for displaying file names in
 * lists, breadcrumbs, or other UI elements where only the name is needed.
 *
 * @param fileId - The unique identifier of the file
 * @param options - Optional TanStack Query options to customize behavior
 * @returns A query object with the filename string, loading state, and error information
 *
 * @example
 * ```typescript
 * // Basic usage
 * const { data: filename, isLoading, error } = useFileName('file-123');
 *
 * // Conditional usage
 * const { data: filename } = useFileName(selectedFileId, {
 *   enabled: !!selectedFileId
 * });
 *
 * // With fallback display
 * const { data: filename = 'Unknown File', isLoading } = useFileName(fileId);
 *
 * // In a component
 * function FileNameDisplay({ fileId }: { fileId: string }) {
 *   const { data: filename, isLoading } = useFileName(fileId);
 *
 *   if (isLoading) return <span>Loading...</span>;
 *   return <span>{filename || 'Unknown File'}</span>;
 * }
 * ```
 */
export function useFileName(
  fileId: string,
  options?: Omit<UseQueryOptions<FileObject, FilesApiServiceError, string>, 'queryKey' | 'queryFn' | 'select'>
) {
  return useQuery({
    queryKey: queryKeys.files.detail(fileId),
    queryFn: () => filesApi.retrieveFile(fileId),
    select: (file: FileObject) => file.filename,
    enabled: !!fileId,
    staleTime: 5 * 60 * 1000,
    retry(_failureCount, error) {
      if (error.code === '404' && (error.details as { detail?: string })?.detail === 'File not found') {
        return false;
      }
      return true;
    },
    ...options,
  });
}

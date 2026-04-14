/**
 * @fileoverview Files feature React hooks for managing file operations.
 *
 * This module provides a comprehensive set of React hooks for interacting with the files API.
 * The hooks are organized into three categories:
 *
 * **Queries (useFilesQueries.ts):**
 * - Data fetching hooks for retrieving file information
 * - Includes file lists, individual file details, and file content
 * - Built with TanStack Query for caching and synchronization
 *
 * **Mutations (useFilesMutations.ts):**
 * - Data modification hooks for file operations
 * - Includes upload, delete, and download functionality
 * - Provides optimistic updates and cache management
 *
 * **Utilities (useFilesUtilities.ts):**
 * - Helper hooks for advanced file management patterns
 * - Enhances user experience with performance optimizations
 *
 * @example
 * ```typescript
 * import {
 *   useFilesList,
 *   useUploadFile,
 * } from '@features/files/hooks';
 *
 * function FileManager() {
 *   const { data: files } = useFilesList();
 *   const uploadFile = useUploadFile();
 *
 *   // Component implementation...
 * }
 * ```
 */

export * from './useFilesQueries';
export * from './useFilesMutations';
export * from './useFilesUtilities';

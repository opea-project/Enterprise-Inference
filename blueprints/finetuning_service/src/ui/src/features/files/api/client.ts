import { config } from '@core/config/appConfig';
import {nextAuthTokenStorage } from '../../auth/api/client';
import type {
  FileObject,
  UploadFileRequest,
  ListFilesParams,
  ListFilesResponse,
  DeleteFileResponse,
  FilesApiError,
  FileExpiresAfter,
} from '../types';

export class FilesApiServiceError extends Error {
  constructor(
    message: string,
    public type: string,
    public code?: string | null,
    public param?: string | null,
    public details?: unknown
  ) {
    super(message);
    this.name = 'FilesApiServiceError';
  }
}

async function filesApiRequest<T>(endpoint: string, options: RequestInit = {}, timeoutMs?: number): Promise<T> {
  const baseUrl = config.endpoints?.files;
  const fullUrl = `${baseUrl}${endpoint}`;
  const token = await nextAuthTokenStorage.get();

  try {
    const headers: Record<string, string> = {};

    // Add JWT token if available
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (options.headers) {
      const existingHeaders = new Headers(options.headers);
      existingHeaders.forEach((value, key) => {
        headers[key] = value;
      });
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    // Setup timeout if specified
    let timeoutId: NodeJS.Timeout | undefined;
    const controller = new AbortController();

    if (timeoutMs) {
      timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    }

    const response = await fetch(fullUrl, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });

    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    const contentType = response.headers.get('content-type');

    if (!response.ok) {
      if (contentType?.includes('application/json')) {
        const errorData = await response.json().catch(() => ({}));
        const error = (errorData as { error?: FilesApiError }).error;
        const detail = (errorData as { detail?: string }).detail;
        throw new FilesApiServiceError(
          detail || error?.message || `HTTP ${response.status}: ${response.statusText}`,
          error?.type || 'api_error',
          'HTTP_ERROR',
          error?.param,
          { ...errorData, status: response.status }
        );
      }

      throw new FilesApiServiceError(
        `HTTP ${response.status}: ${response.statusText}`,
        'http_error',
        'HTTP_ERROR',
        null,
        { status: response.status }
      );
    }

    if (endpoint.includes('/content')) {
      const blob = await response.blob();
      return blob as T;
    }

    if (contentType?.includes('application/json')) {
      const data = await response.json();
      return data as T;
    }

    const text = await response.text();
    return text as T;
  } catch (error) {
    if (error instanceof FilesApiServiceError) {
      throw error;
    }

    throw new FilesApiServiceError(
      error instanceof Error ? error.message : 'Unknown error occurred',
      'network_error',
      'NETWORK_ERROR',
      null,
      error
    );
  }
}

export const filesApi = {
  async uploadFile(
    file: File,
    purpose: UploadFileRequest['purpose'],
    expiresAfter?: FileExpiresAfter
  ): Promise<FileObject> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('purpose', purpose);

    if (expiresAfter) {
      formData.append('expires_after[anchor]', expiresAfter.anchor);
      formData.append('expires_after[seconds]', String(expiresAfter.seconds));
    }

    return filesApiRequest<FileObject>('/v1/files', {
      method: 'POST',
      body: formData,
    });
  },

  async listFiles(params?: ListFilesParams): Promise<ListFilesResponse> {
    const queryParams = new URLSearchParams();

    if (params?.after) {
      queryParams.append('after', params.after);
    }

    if (params?.limit !== undefined) {
      queryParams.append('limit', String(params.limit));
    }

    if (params?.order) {
      queryParams.append('order', params.order);
    }

    if (params?.purpose) {
      queryParams.append('purpose', params.purpose);
    }

    const endpoint = queryParams.toString() ? `/v1/files?${queryParams.toString()}` : '/v1/files';
    return filesApiRequest<ListFilesResponse>(endpoint);
  },

  async retrieveFile(fileId: string): Promise<FileObject> {
    return filesApiRequest<FileObject>(`/v1/files/${fileId}`);
  },

  async deleteFile(fileId: string): Promise<DeleteFileResponse> {
    return filesApiRequest<DeleteFileResponse>(`/v1/files/${fileId}`, {
      method: 'DELETE',
    });
  },

  async retrieveFileContent(fileId: string, timeoutMs?: number): Promise<Blob> {
    return filesApiRequest<Blob>(`/v1/files/${fileId}/content`, {}, timeoutMs);
  },

  async downloadFile(fileId: string, filename?: string): Promise<void> {
    let downloadFilename = filename;
    if (!downloadFilename) {
      const fileInfo = await this.retrieveFile(fileId);
      downloadFilename = fileInfo.filename;
    }

    const blob = await this.retrieveFileContent(fileId, 3600000); // 3600 seconds = 3600000 milliseconds

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  async getFilesByPurpose(purpose: UploadFileRequest['purpose']): Promise<FileObject[]> {
    const response = await this.listFiles({ purpose });
    return response.data;
  },

  async uploadMultipleFiles(
    files: Array<{ file: File; purpose: UploadFileRequest['purpose']; expiresAfter?: FileExpiresAfter }>
  ): Promise<FileObject[]> {
    const uploadPromises = files.map(({ file, purpose, expiresAfter }) =>
      this.uploadFile(file, purpose, expiresAfter)
    );

    return Promise.all(uploadPromises);
  },

  async deleteMultipleFiles(fileIds: string[]): Promise<DeleteFileResponse[]> {
    const deletePromises = fileIds.map((fileId) => this.deleteFile(fileId));
    return Promise.all(deletePromises);
  },
};

export const {
  uploadFile,
  listFiles,
  retrieveFile,
  deleteFile,
  retrieveFileContent,
  downloadFile,
  getFilesByPurpose,
  uploadMultipleFiles,
  deleteMultipleFiles,
} = filesApi;

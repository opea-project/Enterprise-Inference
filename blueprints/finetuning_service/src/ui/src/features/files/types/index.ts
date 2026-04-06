export type FilePurpose = 'assistants' | 'batch' | 'fine-tune' | 'vision' | 'user_data' | 'evals';

export type FileStatus = 'uploaded' | 'processed' | 'error';

export type FileObjectType = 'file';

export type SortOrder = 'asc' | 'desc';

export type ExpirationAnchor = 'created_at' | 'last_accessed_at';

export interface FileExpiresAfter {
  anchor: ExpirationAnchor;
  seconds: number;
}

export interface FileObject {
  id: string;
  object: FileObjectType;
  bytes: number;
  created_at: number;
  expires_at: number | null;
  filename: string;
  purpose: FilePurpose | string;
  status?: FileStatus;
  status_details?: string;
}

export interface UploadFileRequest {
  file: File;
  purpose: FilePurpose;
  expires_after?: FileExpiresAfter;
}

export interface ListFilesParams {
  after?: string;
  limit?: number;
  order?: SortOrder;
  purpose?: FilePurpose;
}

export interface ListFilesResponse {
  object: 'list';
  data: FileObject[];
  first_id: string | null;
  last_id: string | null;
  has_more: boolean;
}

export interface DeleteFileResponse {
  id: string;
  object: FileObjectType;
  deleted: boolean;
}

export interface FilesApiError {
  message: string;
  type: string;
  param?: string | null;
  code?: string | null;
}

export interface FilesApiResponse<T> {
  data?: T;
  error?: FilesApiError;
}

export type ExplorerItemType = 'file' | 'folder';

export interface ExplorerItem {
  id: string;
  name: string;
  path: string;
  type: ExplorerItemType;
  children?: ExplorerItem[];
  expanded?: boolean;
  fileObject?: FileObject;
  size?: number;
  createdAt?: number;
  purpose?: FilePurpose | string;
}

export interface FileTree {
  items: ExplorerItem[];
  totalFiles: number;
  totalFolders: number;
  totalSize: number;
}

export interface ContextMenuItem {
  key: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  divider?: boolean;
}

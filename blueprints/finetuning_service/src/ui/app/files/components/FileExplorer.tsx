'use client';

import { useState, useEffect, useMemo, useCallback, memo, useRef } from 'react';
import {
  Button,
  Space,
  Typography,
  Dropdown,
  Input,
  Tag,
  Card,
  App,
  Breadcrumb,
  Row,
  Col,
  Empty,
  Checkbox
} from 'antd';
import type { MenuProps } from 'antd';
import { notify } from '@notification';
import {
  FolderOutlined,
  FileTextOutlined,
  PlusOutlined,
  DeleteOutlined,
  DownloadOutlined,
  MoreOutlined,
  CloudUploadOutlined,
  ReloadOutlined,
  HomeOutlined
} from '@ant-design/icons';
import { ExplorerItem, FileObject } from '@features/files/types';
import { useDeleteFile, useDownloadFile } from '@features/files/hooks';
import { config } from '@/src/core/config/appConfig';

const { Text, Title } = Typography;

const EMPTY_STRING_ARRAY: string[] = [];

// Constants
const PURPOSE_COLORS: Record<string, string> = {
  'fine-tune': 'blue',
  'assistants': 'green',
  'batch': 'orange',
  'vision': 'purple',
  'user_data': 'cyan',
  'evals': 'magenta',
};

const BYTE_SIZES = ['B', 'KB', 'MB', 'GB'] as const;
const BYTE_BASE = 1024;

// Utility functions
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const i = Math.floor(Math.log(bytes) / Math.log(BYTE_BASE));
  return `${Math.round((bytes / Math.pow(BYTE_BASE, i)) * 100) / 100} ${BYTE_SIZES[i]}`;
};

const getPurposeColor = (purpose: string): string => PURPOSE_COLORS[purpose] || 'default';

const splitPath = (path: string, separator: string): string[] => path.split(separator);

const joinPath = (parts: string[], separator: string): string => parts.join(separator);

const getParentPath = (path: string, separator: string): string => {
  const parts = splitPath(path, separator);
  return parts.length > 1 ? joinPath(parts.slice(0, -1), separator) : '';
};

const getFileExtension = (filename: string): string => {
  const lastDot = filename.lastIndexOf('.');
  return lastDot > 0 ? filename.substring(lastDot + 1).toLowerCase() : '';
};



// Memoized File Item Component
const FileItem = memo<{
  item: ExplorerItem;
  enableSelection: boolean;
  isSelected: boolean;
  onSelectionToggle: (id: string) => void;
  onContextMenu: (key: string, item: ExplorerItem) => void;
  getMenuItems: (item: ExplorerItem) => MenuProps['items'];
}>(({ item, enableSelection, isSelected, onSelectionToggle, onContextMenu, getMenuItems }) => (
  <Col xs={12} sm={8} md={6} lg={3} xl={2}>
    <div
      style={{
        textAlign: 'center',
        padding: 8,
        borderRadius: 8,
        transition: 'background-color 0.2s',
        position: 'relative',
        border: enableSelection && isSelected ? '2px solid #52c41a' : '2px solid transparent',
        backgroundColor: enableSelection && isSelected ? '#f6ffed' : 'transparent',
      }}
      onMouseEnter={(e) => {
        if (!enableSelection || !isSelected) {
          e.currentTarget.style.backgroundColor = '#f5f5f5';
        }
      }}
      onMouseLeave={(e) => {
        if (!enableSelection || !isSelected) {
          e.currentTarget.style.backgroundColor = enableSelection && isSelected ? '#f6ffed' : 'transparent';
        }
      }}
    >
      {enableSelection && (
        <div style={{ position: 'absolute', top: 4, left: 4 }}>
          <Checkbox
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelectionToggle(item.id);
            }}
          />
        </div>
      )}
      {!enableSelection && (
        <div style={{ position: 'absolute', top: 2, right: 2 }}>
          <Dropdown
            menu={{
              items: getMenuItems(item) ?? [],
              onClick: ({ key }) => onContextMenu(key as string, item),
            }}
            trigger={['click']}
            placement="bottomRight"
          >
            <Button
              type="text"
              size="small"
              icon={<MoreOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Dropdown>
        </div>
      )}
      <FileTextOutlined style={{ fontSize: 32, color: '#52c41a' }} />
      <div style={{ marginTop: 4, wordBreak: 'break-word', fontSize: 13 }}>
        <Text strong>{item.name}</Text>
      </div>
      {item.purpose && (
        <div style={{ marginTop: 3 }}>
          <Tag color={getPurposeColor(item.purpose)} style={{ fontSize: 9 }}>
            {item.purpose}
          </Tag>
        </div>
      )}
      {item.size && (
        <div style={{ marginTop: 3 }}>
          <Text type="secondary" style={{ fontSize: 10 }}>
            {formatBytes(item.size)}
          </Text>
        </div>
      )}
    </div>
  </Col>
));
FileItem.displayName = 'FileItem';

// Memoized Folder Item Component
const FolderItem = memo<{
  folder: ExplorerItem;
  enableSelection: boolean;
  isSelected: boolean;
  onFolderClick: (path: string) => void;
  onSelectionToggle: (path: string) => void;
}>(({ folder, enableSelection, isSelected, onFolderClick, onSelectionToggle }) => (
  <Col xs={12} sm={8} md={6} lg={3} xl={2}>
    <div
      style={{
        textAlign: 'center',
        cursor: 'pointer',
        padding: 8,
        borderRadius: 8,
        transition: 'background-color 0.2s',
        position: 'relative',
        border: enableSelection && isSelected ? '2px solid #1890ff' : '2px solid transparent',
        backgroundColor: enableSelection && isSelected ? '#e6f7ff' : 'transparent',
      }}
      onClick={(e) => {
        if (enableSelection && e.target !== e.currentTarget && (e.target as HTMLElement).tagName !== 'INPUT') {
          return;
        }
        if (!enableSelection) {
          onFolderClick(folder.path);
        }
      }}
      onMouseEnter={(e) => {
        if (!enableSelection || !isSelected) {
          e.currentTarget.style.backgroundColor = '#f5f5f5';
        }
      }}
      onMouseLeave={(e) => {
        if (!enableSelection || !isSelected) {
          e.currentTarget.style.backgroundColor = enableSelection && isSelected ? '#e6f7ff' : 'transparent';
        }
      }}
    >
      {enableSelection && (
        <div style={{ position: 'absolute', top: 4, left: 4 }}>
          <Checkbox
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelectionToggle(folder.path);
            }}
          />
        </div>
      )}
      <div
        onClick={(e) => {
          if (!enableSelection) return;
          e.stopPropagation();
          onFolderClick(folder.path);
        }}
      >
        <FolderOutlined style={{ fontSize: 32, color: '#1890ff' }} />
        <div style={{ marginTop: 4, wordBreak: 'break-word', fontSize: 13 }}>
          <Text strong>{folder.name}</Text>
        </div>
      </div>
    </div>
  </Col>
));
FolderItem.displayName = 'FolderItem';

interface FileExplorerProps {
  files: FileObject[];
  loading: boolean;
  onRefresh: () => void;
  onUploadToFolder: (folderPath: string) => void;
  onUploadToRoot: () => void;
  onFolderCreated?: (folderPath: string) => void;
  pathSeparator?: string;
  enableSelection?: boolean;
  onSelect?: (selectedFiles: FileObject[]) => void;
  maxSelection?: number; // Maximum number of files that can be selected (undefined = unlimited)
  // Filter props
  showOnlyFileTypes?: string[];
  excludeFileTypes?: string[];
  onFileTypeFiltersChange?: (showOnly: string[], exclude: string[]) => void;
}

const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  loading,
  onRefresh,
  onUploadToFolder,
  onUploadToRoot,
  onFolderCreated,
  pathSeparator = config.filePathSeperator,
  enableSelection = true,
  onSelect,
  maxSelection,
  showOnlyFileTypes = EMPTY_STRING_ARRAY,
  excludeFileTypes = EMPTY_STRING_ARRAY,

}) => {
  const { modal } = App.useApp();

  // Hooks for file operations
  const deleteFileMutation = useDeleteFile();
  const downloadFileMutation = useDownloadFile();

  const [currentPath, setCurrentPath] = useState<string>('');
  const [virtualFolders, setVirtualFolders] = useState<Set<string>>(new Set());
  const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(new Set());
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set());

  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Get all files in a folder (including subfolders)
  const getFilesInFolder = useCallback((folderPath: string): FileObject[] => {
    const prefix = `${folderPath}${pathSeparator}`;
    return files.filter(file => {
      if (!file.filename) return false;
      return file.filename.startsWith(prefix) ||
        getParentPath(file.filename, pathSeparator) === folderPath;
    });
  }, [files, pathSeparator]);

  // Get all child folders of a given folder (including nested subfolders)
  const getChildFolders = useCallback((folderPath: string): string[] => {
    const prefix = `${folderPath}${pathSeparator}`;
    const childFolders: string[] = [];

    // Get all unique folder paths from files
    const allFolderPaths = new Set<string>();
    files.forEach((file) => {
      if (!file.filename) return;
      const pathParts = file.filename.split(pathSeparator);
      if (pathParts.length > 1) {
        let currentFolderPath = '';
        for (let i = 0; i < pathParts.length - 1; i++) {
          currentFolderPath = currentFolderPath ? `${currentFolderPath}${pathSeparator}${pathParts[i]}` : pathParts[i];
          allFolderPaths.add(currentFolderPath);
        }
      }
    });

    // Add virtual folders
    virtualFolders.forEach(path => allFolderPaths.add(path));

    // Filter child folders
    allFolderPaths.forEach(path => {
      if (path.startsWith(prefix)) {
        childFolders.push(path);
      }
    });

    return childFolders;
  }, [files, pathSeparator, virtualFolders]);

  // Get all selected files (individual files + files in selected folders)
  const getSelectedFiles = useCallback((fileIds: Set<string>, folderPaths: Set<string>): FileObject[] => {
    const result: FileObject[] = [];
    const addedIds = new Set<string>();

    // Add individually selected files
    fileIds.forEach(fileId => {
      const file = files.find(f => f.id === fileId);
      if (file && !addedIds.has(file.id)) {
        result.push(file);
        addedIds.add(file.id);
      }
    });

    // Add files from selected folders
    if (folderPaths.size > 0) {
      files.forEach(file => {
        if (!file.filename || addedIds.has(file.id)) return;

        const parentPath = getParentPath(file.filename, pathSeparator);
        for (const folderPath of folderPaths) {
          if (file.filename.startsWith(`${folderPath}${pathSeparator}`) || parentPath === folderPath) {
            result.push(file);
            addedIds.add(file.id);
            break;
          }
        }
      });
    }

    return result;
  }, [files, pathSeparator]);

  // Effect to call onSelect whenever selection changes
  useEffect(() => {
    if (onSelectRef.current) {
      const selectedFiles = getSelectedFiles(selectedFileIds, selectedFolders);
      onSelectRef.current(selectedFiles);
    }
  }, [selectedFileIds, selectedFolders, getSelectedFiles]);



  // Filter files based on file type filters
  const filteredFiles = useMemo(() => {
    return files.filter(file => {
      if (!file.filename) return true;

      const extension = getFileExtension(file.filename);
      if (!extension) return true; // Files without extensions are always shown

      // If showOnly filter is active, only show files with those extensions
      if (showOnlyFileTypes.length > 0) {
        return showOnlyFileTypes.includes(extension);
      }

      // If exclude filter is active, hide files with those extensions
      if (excludeFileTypes.length > 0) {
        return !excludeFileTypes.includes(extension);
      }

      return true;
    });
  }, [files, showOnlyFileTypes, excludeFileTypes]);



  // Get items in current folder
  const currentItems = useMemo((): { folders: ExplorerItem[]; files: ExplorerItem[] } => {
    const folders: ExplorerItem[] = [];
    const filesInFolder: ExplorerItem[] = [];

    // Get all unique folder paths
    const allFolderPaths = new Set<string>();

    // Add folders from existing files (using filtered files)
    filteredFiles.forEach((file) => {
      if (!file.filename) return; // Skip files without filename

      const pathParts = file.filename.split(pathSeparator);
      if (pathParts.length > 1) {
        let currentFolderPath = '';
        for (let i = 0; i < pathParts.length - 1; i++) {
          currentFolderPath = currentFolderPath ? `${currentFolderPath}${pathSeparator}${pathParts[i]}` : pathParts[i];
          allFolderPaths.add(currentFolderPath);
        }
      }
    });

    // Add virtual folders
    virtualFolders.forEach(path => allFolderPaths.add(path));

    // Filter items for current path
    if (currentPath === '') {
      // Root level - show top-level folders and files
      allFolderPaths.forEach(folderPath => {
        if (!folderPath.includes(pathSeparator)) {
          // Top-level folder
          folders.push({
            id: `folder-${folderPath}`,
            name: folderPath,
            path: folderPath,
            type: 'folder',
          });
        }
      });

      // Add root-level files (using filtered files)
      filteredFiles.forEach(file => {
        if (!file.filename) return; // Skip files without filename

        if (!file.filename.includes(pathSeparator)) {
          filesInFolder.push({
            id: file.id,
            name: file.filename,
            path: file.filename,
            type: 'file',
            fileObject: file,
            size: file.bytes,
            createdAt: file.created_at,
            purpose: file.purpose,
          });
        }
      });
    } else {
      // Inside a folder - show subfolders and files in this folder
      allFolderPaths.forEach(folderPath => {
        if (folderPath.startsWith(currentPath + pathSeparator)) {
          const relativePath = folderPath.substring(currentPath.length + 1);
          if (!relativePath.includes(pathSeparator)) {
            // Direct subfolder
            folders.push({
              id: `folder-${folderPath}`,
              name: relativePath,
              path: folderPath,
              type: 'folder',
            });
          }
        }
      });

      // Add files in current folder (using filtered files)
      filteredFiles.forEach(file => {
        if (!file.filename) return; // Skip files without filename

        if (file.filename.startsWith(currentPath + pathSeparator)) {
          const relativePath = file.filename.substring(currentPath.length + 1);
          if (!relativePath.includes(pathSeparator)) {
            // File directly in this folder
            const fileName = relativePath;
            filesInFolder.push({
              id: file.id,
              name: fileName,
              path: file.filename,
              type: 'file',
              fileObject: file,
              size: file.bytes,
              createdAt: file.created_at,
              purpose: file.purpose,
            });
          }
        }
      });
    }

    // Sort folders and files alphabetically
    folders.sort((a, b) => a.name.localeCompare(b.name));
    filesInFolder.sort((a, b) => a.name.localeCompare(b.name));

    return { folders, files: filesInFolder };
  }, [filteredFiles, currentPath, virtualFolders, pathSeparator]);

  // Get breadcrumb items
  const breadcrumbItems = useMemo(() => {
    const items = [
      {
        title: (
          <span onClick={() => setCurrentPath('')} style={{ cursor: 'pointer' }}>
            <HomeOutlined /> Root
          </span>
        ),
      },
    ];

    if (currentPath) {
      const pathParts = currentPath.split(pathSeparator);
      pathParts.forEach((part, index) => {
        const path = pathParts.slice(0, index + 1).join(pathSeparator);
        items.push({
          title: (
            <span onClick={() => setCurrentPath(path)} style={{ cursor: 'pointer' }}>
              {part}
            </span>
          ),
        });
      });
    }

    return items;
  }, [currentPath, pathSeparator]);

  // Navigate to folder
  const handleFolderClick = useCallback((folderPath: string) => {
    setCurrentPath(folderPath);
  }, []);

  // Handle file selection toggle - optimized
  const handleFileSelectionToggle = useCallback((fileId: string) => {
    const file = files.find(f => f.id === fileId);
    if (!file?.filename) return;

    const isCurrentlySelected = selectedFileIds.has(fileId);
    const parentFolderPath = getParentPath(file.filename, pathSeparator);

    if (isCurrentlySelected) {
      // Deselecting a file
      setSelectedFileIds(prev => {
        const updated = new Set(prev);
        updated.delete(fileId);
        return updated;
      });

      // If parent folder is selected, deselect it and select all other files individually
      if (parentFolderPath && selectedFolders.has(parentFolderPath)) {
        const filesInFolder = getFilesInFolder(parentFolderPath);
        const childFolders = getChildFolders(parentFolderPath);

        setSelectedFolders(prev => {
          const updated = new Set(prev);
          updated.delete(parentFolderPath);
          // Also deselect all child folders
          childFolders.forEach(childPath => updated.delete(childPath));
          return updated;
        });

        setSelectedFileIds(prev => {
          const updated = new Set(prev);
          filesInFolder.forEach(f => {
            if (f.id !== fileId) updated.add(f.id);
          });
          return updated;
        });
      }
    } else {
      // Selecting a file - check maxSelection limit first
      if (maxSelection && selectedFileIds.size >= maxSelection) {
        // If at max selection limit, replace the first selected file with the new one
        if (maxSelection === 1) {
          // For single selection, clear all and add new one
          setSelectedFileIds(new Set([fileId]));
          return;
        } else {
          // For multiple selection, don't allow more selections
          return;
        }
      }

      // Selecting a file - add it to selected files
      setSelectedFileIds(prev => {
        const updated = new Set(prev).add(fileId);

        // Check if all items in parent folder are now selected
        if (parentFolderPath) {
          const filesInFolder = getFilesInFolder(parentFolderPath);
          const childFolders = getChildFolders(parentFolderPath);

          // Get direct children only (not nested subfolders)
          const directChildFolders = childFolders.filter(childPath => {
            const relativePath = childPath.substring(parentFolderPath.length + 1);
            return !relativePath.includes(pathSeparator);
          });

          // Check if all files in this folder are selected
          const allFilesSelected = filesInFolder.every(f =>
            updated.has(f.id) || getParentPath(f.filename, pathSeparator) !== parentFolderPath
          );

          // Check if all direct child folders are selected
          const allChildFoldersSelected = directChildFolders.every(childPath =>
            selectedFolders.has(childPath)
          );

          // If all children are selected, select the parent folder
          if (allFilesSelected && allChildFoldersSelected && (filesInFolder.length > 0 || directChildFolders.length > 0)) {
            // Remove individual file selections and select the parent folder
            filesInFolder.forEach(f => updated.delete(f.id));
            setSelectedFolders(prevFolders => {
              const newFolders = new Set(prevFolders);
              newFolders.add(parentFolderPath);
              // Add all nested child folders too
              childFolders.forEach(childPath => newFolders.add(childPath));
              return newFolders;
            });
          }
        }

        return updated;
      });
    }
  }, [files, selectedFileIds, selectedFolders, pathSeparator, getFilesInFolder, getChildFolders, maxSelection]);

  // Handle folder selection toggle - optimized
  const handleFolderSelectionToggle = useCallback((folderPath: string) => {
    const isCurrentlySelected = selectedFolders.has(folderPath);
    const filesInFolder = getFilesInFolder(folderPath);
    const childFolders = getChildFolders(folderPath);
    const parentFolderPath = getParentPath(folderPath, pathSeparator);

    if (isCurrentlySelected) {
      // Deselecting folder - remove folder and all child folders from selection
      setSelectedFolders(prev => {
        const newSelected = new Set(prev);
        newSelected.delete(folderPath);
        // Remove all child folders
        childFolders.forEach(childPath => newSelected.delete(childPath));
        return newSelected;
      });

      // Remove all files in this folder from individual selection
      setSelectedFileIds(prev => {
        const updated = new Set(prev);
        filesInFolder.forEach(f => updated.delete(f.id));
        return updated;
      });
    } else {
      // Selecting folder - check if it would exceed maxSelection limit
      if (maxSelection) {
        const filesInFolder = getFilesInFolder(folderPath);
        const totalFilesInSelection = filesInFolder.length;

        if (selectedFileIds.size + totalFilesInSelection > maxSelection) {
          // Don't allow folder selection if it would exceed the limit
          return;
        }
      }

      // Selecting folder - add folder and all child folders to selection
      setSelectedFolders(prev => {
        const newSelected = new Set(prev);
        newSelected.add(folderPath);
        // Add all child folders
        childFolders.forEach(childPath => newSelected.add(childPath));

        // Check if all siblings are now selected - auto-select parent
        if (parentFolderPath) {
          const parentChildFolders = getChildFolders(parentFolderPath);
          const directParentChildFolders = parentChildFolders.filter(childPath => {
            const relativePath = childPath.substring(parentFolderPath.length + 1);
            return !relativePath.includes(pathSeparator);
          });

          const filesInParent = getFilesInFolder(parentFolderPath);

          // Check if all direct child folders are selected (including the one we just selected)
          const allChildFoldersSelected = directParentChildFolders.every(childPath =>
            childPath === folderPath || newSelected.has(childPath)
          );

          // Check if all files in parent are selected
          const allFilesSelected = filesInParent.every(f => {
            const fileParentPath = getParentPath(f.filename, pathSeparator);
            return fileParentPath !== parentFolderPath || selectedFileIds.has(f.id);
          });

          if (allChildFoldersSelected && allFilesSelected && (filesInParent.length > 0 || directParentChildFolders.length > 0)) {
            // Select parent folder and all its nested children
            const allParentChildren = getChildFolders(parentFolderPath);
            newSelected.add(parentFolderPath);
            allParentChildren.forEach(childPath => newSelected.add(childPath));
          }
        }

        return newSelected;
      });

      // Remove individual file selections within this folder since folder is now selected
      setSelectedFileIds(prev => {
        const updated = new Set(prev);
        filesInFolder.forEach(f => updated.delete(f.id));
        return updated;
      });
    }
  }, [getFilesInFolder, getChildFolders, selectedFolders, selectedFileIds, pathSeparator, maxSelection]);

  // Check if a file is selected (either individually or via folder selection) - optimized
  const isFileSelected = useCallback((fileId: string, filePath: string): boolean => {
    if (selectedFileIds.has(fileId)) return true;

    // Check if any parent folder is selected
    const pathParts = splitPath(filePath, pathSeparator);
    for (let i = 1; i < pathParts.length; i++) {
      if (selectedFolders.has(joinPath(pathParts.slice(0, i), pathSeparator))) return true;
    }

    return false;
  }, [selectedFileIds, selectedFolders, pathSeparator]);

  // Check if a folder is selected - optimized
  const isFolderSelected = useCallback((folderPath: string): boolean => {
    return selectedFolders.has(folderPath);
  }, [selectedFolders]);

  // Handle file download - optimized
  const handleDownload = useCallback(async (fileId: string, filename: string) => {
    try {
      await downloadFileMutation.mutateAsync({ fileId, filename });
      notify.success({ message: 'File downloaded successfully' });
    } catch (error) {
      notify.error({ message: error instanceof Error ? error.message : 'Failed to download file' });
    }
  }, [downloadFileMutation]);

  // Handle file delete - optimized
  const handleDelete = useCallback(async (file: FileObject, filename: string) => {
    modal.confirm({
      title: 'Delete File',
      content: `Are you sure you want to delete "${filename}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        return deleteFileMutation.mutateAsync(file).then(() => {
          notify.success({ message: 'File deleted successfully' });
          // Remove file from selection if it was selected
          setSelectedFileIds(prev => {
            const updated = new Set(prev);
            updated.delete(file.id);
            return updated;
          });
        }).catch(error => {
          notify.error({ message: error instanceof Error ? error.message : 'Failed to delete file' });
          throw error; // Re-throw to prevent modal from closing on error
        });
      },
    });
  }, [modal, deleteFileMutation]);

  // Get context menu items for a file - static
  const fileContextMenuItems = useMemo<MenuProps['items']>(() => [
    {
      key: 'download',
      label: 'Download',
      icon: <DownloadOutlined />,
    },
    {
      key: 'delete',
      label: <span style={{ color: '#ff4d4f' }}>Delete</span>,
      icon: <DeleteOutlined style={{ color: '#ff4d4f' }} />,
    }
  ], []);

  // Handle file context menu clicks - optimized
  const handleFileContextMenuClick = useCallback((key: string, item: ExplorerItem) => {
    if (!item.fileObject) return;

    if (key === 'download') {
      handleDownload(item.fileObject.id, item.fileObject.filename);
    } else if (key === 'delete') {
      handleDelete(item.fileObject, item.name);
    }
  }, [handleDelete, handleDownload]);

  // Handle folder creation - optimized
  const handleCreateFolder = useCallback(() => {
    let folderName = '';
    let modalInstance: ReturnType<typeof modal.confirm> | null = null;

    const validateFolderName = (name: string): string | null => {
      if (!name.trim()) return 'Please enter a folder name';
      if (/[<>:"/\\|?*]/.test(name)) return 'Folder name contains invalid characters';

      const newFolderPath = currentPath ? `${currentPath}${pathSeparator}${name.trim()}` : name.trim();

      if (virtualFolders.has(newFolderPath)) return 'Folder already exists';

      // Check if any existing file creates this folder structure
      const folderExists = files.some(file => {
        if (!file.filename) return false;
        const fileFolderPath = getParentPath(file.filename, pathSeparator);
        return fileFolderPath === newFolderPath || fileFolderPath.startsWith(`${newFolderPath}${pathSeparator}`);
      });

      return folderExists ? 'Folder already exists' : null;
    };

    const createFolder = () => {
      const validationError = validateFolderName(folderName);
      if (validationError) {
        notify.error({ message: validationError });
        return Promise.reject(new Error(validationError));
      }

      const newFolderPath = currentPath ? `${currentPath}${pathSeparator}${folderName.trim()}` : folderName.trim();
      setVirtualFolders(prev => new Set([...prev, newFolderPath]));
      notify.success({ message: `Folder "${folderName}" created` });

      if (onFolderCreated) {
        onFolderCreated(newFolderPath);
      }

      // Explicitly destroy the modal to ensure it closes
      if (modalInstance) {
        modalInstance.destroy();
      }

      return Promise.resolve();
    };

    const content = (
      <div style={{ marginTop: 16 }}>
        {currentPath && (
          <div style={{ marginBottom: 12 }}>
            <Typography.Text>Creating folder in: </Typography.Text>
            <Typography.Text code>{currentPath || 'Root'}</Typography.Text>
          </div>
        )}
        <div>
          <Typography.Text strong>Folder Name:</Typography.Text>
          <Input
            placeholder="Enter folder name"
            onChange={(e) => { folderName = e.target.value; }}
            style={{ marginTop: 8 }}
            autoFocus
            onPressEnter={() => {
              createFolder().catch(() => {
                // Modal will stay open on error, which is the desired behavior
              });
            }}
          />
        </div>
      </div>
    );

    modalInstance = modal.confirm({
      title: 'Create New Folder',
      content,
      okText: 'Create',
      cancelText: 'Cancel',
      onOk: createFolder,
    });
  }, [currentPath, pathSeparator, virtualFolders, files, modal, onFolderCreated]);

  return (
    <div style={{ height: '100%' }}>
      {/* Header */}
      <div style={{
        marginBottom: 16,
        padding: '0 8px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}>
          <Title level={4} style={{ margin: 0 }}>Files Explorer</Title>

          {!enableSelection && (
            <Space>
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={onRefresh}
              >
                Refresh
              </Button>
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={handleCreateFolder}
              >
                New Folder
              </Button>
              <Button
                type="primary"
                size="small"
                icon={<CloudUploadOutlined />}
                onClick={() => currentPath ? onUploadToFolder(currentPath) : onUploadToRoot()}
              >
                Upload File
              </Button>
            </Space>
          )}
        </div>
      </div>
      {/* Grid View */}
      <Card styles={{ body: { padding: 16 } }} loading={loading || deleteFileMutation.isPending}>
        {/* Breadcrumb inside the box */}
        <div style={{ marginBottom: 16 }}>
          <Breadcrumb items={breadcrumbItems} />
        </div>

        {currentItems.folders.length === 0 && currentItems.files.length === 0 ? (
          <Empty description="No files or folders" />
        ) : (
          <Row gutter={[8, 8]}>
            {/* Render Folders */}
            {currentItems.folders.map((folder) => (
              <FolderItem
                key={folder.id}
                folder={folder}
                enableSelection={enableSelection}
                isSelected={isFolderSelected(folder.path)}
                onFolderClick={handleFolderClick}
                onSelectionToggle={handleFolderSelectionToggle}
              />
            ))}

            {/* Render Files */}
            {currentItems.files.map((file) => (
              <FileItem
                key={file.id}
                item={file}
                enableSelection={enableSelection}
                isSelected={isFileSelected(file.id, file.path)}
                onSelectionToggle={handleFileSelectionToggle}
                onContextMenu={handleFileContextMenuClick}
                getMenuItems={() => fileContextMenuItems}
              />
            ))}
          </Row>
        )}
      </Card>
    </div>
  );
};

export default FileExplorer;
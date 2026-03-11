import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, X } from 'lucide-react'

const FileUpload = ({ onFileSelect, multiple = false, maxFiles = 5 }) => {
  const [files, setFiles] = useState([])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 10 * 1024 * 1024,
    multiple: multiple,
    maxFiles: multiple ? maxFiles : 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        if (multiple) {
          const newFiles = [...files, ...acceptedFiles].slice(0, maxFiles)
          setFiles(newFiles)
          onFileSelect(newFiles)
        } else {
          const selectedFile = acceptedFiles[0]
          setFiles([selectedFile])
          onFileSelect(selectedFile)
        }
      }
    },
    onDropRejected: (rejections) => {
      const rejection = rejections[0]
      if (rejection.errors[0].code === 'file-too-large') {
        alert('File size must be less than 10MB')
      } else if (rejection.errors[0].code === 'too-many-files') {
        alert(`Maximum ${maxFiles} files allowed`)
      } else {
        alert('Please upload PDF files only')
      }
    },
  })

  const handleRemove = (indexToRemove) => {
    if (multiple) {
      const newFiles = files.filter((_, index) => index !== indexToRemove)
      setFiles(newFiles)
      onFileSelect(newFiles)
    } else {
      setFiles([])
      onFileSelect(null)
    }
  }

  return (
    <div>
      <div
        {...getRootProps()}
        className={`file-drop-zone ${
          isDragActive ? 'file-drop-zone-active' : 'file-drop-zone-inactive'
        }`}
      >
        <input {...getInputProps()} />
        {files.length === 0 ? (
          <>
            <Upload className="mx-auto h-16 w-16 text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">
              {multiple ? `Drop your files here or click to browse` : `Drop your file here or click to browse`}
            </p>
            <p className="text-sm text-gray-500 mb-2">Supported formats: PDF</p>
            <p className="text-xs text-gray-400">
              Maximum file size: 10MB{multiple ? ` • Maximum ${maxFiles} files` : ''}
            </p>
          </>
        ) : (
          <div className="w-full">
            <p className="text-sm text-gray-600 mb-2 text-center">
              {files.length} file{files.length > 1 ? 's' : ''} selected
              {multiple && ` (max ${maxFiles})`}
            </p>
          </div>
        )}
      </div>

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between bg-white p-3 rounded-lg border border-gray-200"
            >
              <div className="flex items-center space-x-3">
                <FileText className="h-6 w-6 text-primary-600 flex-shrink-0" />
                <div className="text-left min-w-0 flex-1">
                  <p className="font-medium text-gray-800 truncate">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleRemove(index)
                }}
                className="text-gray-400 hover:text-red-500 transition-colors ml-2 flex-shrink-0"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default FileUpload

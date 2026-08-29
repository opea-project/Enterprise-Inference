import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, XCircle, AlertCircle, CheckCircle, Loader, FileText, Eye, Download, FileJson, FileSpreadsheet } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import ExtractionStatus from '../components/ExtractionStatus'
import ErrorMessage from '../components/ErrorMessage'
import { uploadDocument, batchUploadDocuments, extractData, getTemplates } from '../services/api'

const UploadPage = () => {
  const navigate = useNavigate()
  const [files, setFiles] = useState([])
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [batchJobs, setBatchJobs] = useState([])
  const [errorMessage, setErrorMessage] = useState(null)
  const [error, setError] = useState(null)
  const [viewModalResult, setViewModalResult] = useState(null)

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    try {
      const response = await getTemplates()
      console.log('Templates response:', response)

      // Handle both array and object responses
      const templateList = Array.isArray(response) ? response : (response.templates || [])

      setTemplates(templateList)
      if (templateList.length > 0) {
        setSelectedTemplate(templateList[0].id)
      }
    } catch (error) {
      console.error('Error loading templates:', error)
      setError('Failed to load templates. Please try refreshing the page.')
    }
  }

  const handleFileSelect = (selectedFiles) => {
    setError(null)
    setFiles(Array.isArray(selectedFiles) ? selectedFiles : [selectedFiles])
  }

  const handleUploadAndExtract = async () => {
    if (!files || files.length === 0) {
      setError('Please select at least one file')
      return
    }
    if (!selectedTemplate) {
      setError('Please select a document type')
      return
    }

    setIsLoading(true)
    setErrorMessage(null)
    setBatchJobs([])

    try {
      // Single file - use single upload
      if (files.length === 1) {
        const uploadResponse = await uploadDocument(files[0])
        const extractResponse = await extractData(uploadResponse.document_id, selectedTemplate)

        // Track as single job
        setBatchJobs([{
          filename: files[0].name,
          success: true,
          documentId: uploadResponse.document_id,
          error: null,
          jobId: extractResponse.id,
          status: 'processing',
          extractionResult: null
        }])
      } else {
        // Multiple files - use batch upload
        const uploadResponse = await batchUploadDocuments(files)

        // Initialize batch jobs tracking
        const jobs = uploadResponse.results.map(result => ({
          filename: result.filename,
          success: result.success,
          documentId: result.document_id,
          error: result.error,
          jobId: null,
          status: result.success ? 'pending' : 'failed',
          extractionResult: null
        }))

        setBatchJobs(jobs)

        // Start extraction for successful uploads
        const successfulUploads = jobs.filter(job => job.success)

        for (let i = 0; i < successfulUploads.length; i++) {
          const job = successfulUploads[i]
          try {
            const extractResponse = await extractData(job.documentId, selectedTemplate)

            // Update job with extraction ID
            setBatchJobs(prev => prev.map(j =>
              j.filename === job.filename
                ? { ...j, jobId: extractResponse.id, status: 'processing' }
                : j
            ))
          } catch (error) {
            console.error(`Error starting extraction for ${job.filename}:`, error)
            setBatchJobs(prev => prev.map(j =>
              j.filename === job.filename
                ? { ...j, status: 'failed', error: error.message }
                : j
            ))
          }
        }
      }
    } catch (error) {
      console.error('Error processing documents:', error)
      setErrorMessage(error.response?.data?.detail || error.message || 'Failed to process documents')
      setIsLoading(false)
    }
  }

  const handleBatchJobComplete = (jobId, result) => {
    setBatchJobs(prev => prev.map(j =>
      j.jobId === jobId
        ? { ...j, status: 'completed', extractionResult: result }
        : j
    ))

    // Check if all jobs are complete
    const updatedJobs = batchJobs.map(j =>
      j.jobId === jobId ? { ...j, status: 'completed' } : j
    )

    const allComplete = updatedJobs.every(j =>
      j.status === 'completed' || j.status === 'failed'
    )

    if (allComplete) {
      setIsLoading(false)
    }
  }

  const handleBatchJobError = (jobId, error) => {
    setBatchJobs(prev => prev.map(j =>
      j.jobId === jobId
        ? { ...j, status: 'failed', error }
        : j
    ))
  }

  const handleViewResults = (job) => {
    console.log('handleViewResults called with job:', job)
    if (job && job.extractionResult) {
      console.log('Setting viewModalResult:', job.extractionResult)
      setViewModalResult(job.extractionResult)
    } else {
      console.error('No extraction result found in job')
      setError('Unable to view results - extraction data not available')
    }
  }

  const handleDownloadJSON = (job) => {
    if (!job.extractionResult) return

    const dataStr = JSON.stringify(job.extractionResult.extracted_data, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${job.filename.replace('.pdf', '')}_extraction.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleDownloadCSV = (job) => {
    if (!job.extractionResult || !job.extractionResult.extracted_data) return

    const data = job.extractionResult.extracted_data
    const headers = Object.keys(data)
    const values = Object.values(data).map(v => {
      if (v === null || v === undefined) return ''
      if (Array.isArray(v) || typeof v === 'object') {
        return JSON.stringify(v)
      }
      return String(v)
    })

    let csvContent = headers.join(',') + '\n'
    csvContent += values.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')

    const dataBlob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${job.filename.replace('.pdf', '')}_extraction.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleBatchExportJSON = () => {
    const completedJobs = batchJobs.filter(j => j.status === 'completed' && j.extractionResult)

    if (completedJobs.length === 0) {
      setError('No completed extractions to export')
      return
    }

    const batchData = completedJobs.map(job => ({
      filename: job.filename,
      extracted_data: job.extractionResult.extracted_data,
      metadata: {
        coverage: job.extractionResult.field_coverage_percent,
        stage_used: job.extractionResult.stage_used,
        processing_time_ms: job.extractionResult.processing_time_ms
      }
    }))

    const dataStr = JSON.stringify(batchData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `batch_extraction_${Date.now()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleBatchExportCSV = () => {
    const completedJobs = batchJobs.filter(j => j.status === 'completed' && j.extractionResult)

    if (completedJobs.length === 0) {
      setError('No completed extractions to export')
      return
    }

    // Get all unique field names across all extractions
    const allFields = new Set()
    completedJobs.forEach(job => {
      Object.keys(job.extractionResult.extracted_data).forEach(field => allFields.add(field))
    })

    const fieldNames = ['filename', ...Array.from(allFields)]

    // Build CSV
    let csvContent = fieldNames.join(',') + '\n'

    completedJobs.forEach(job => {
      const data = job.extractionResult.extracted_data
      const row = [
        `"${job.filename}"`,
        ...Array.from(allFields).map(field => {
          const value = data[field]
          if (value === undefined || value === null) return '""'

          // Serialize arrays/objects as JSON
          if (Array.isArray(value) || typeof value === 'object') {
            return `"${JSON.stringify(value).replace(/"/g, '""')}"`
          }

          return `"${String(value).replace(/"/g, '""')}"`
        })
      ]
      csvContent += row.join(',') + '\n'
    })

    const dataBlob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `batch_extraction_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Extract Data from Documents
        </h1>
        <p className="text-gray-600">
          Upload up to 5 documents at once to extract structured data
        </p>
      </div>

      {/* Error Messages */}
      <ErrorMessage message={error} type="error" onClose={() => setError(null)} />

      <div className="flex-1 flex items-center justify-center">
        <div className="card max-w-3xl w-full">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Document Type:
              </label>
              <select
                value={selectedTemplate}
                onChange={(e) => {
                  setError(null)
                  setSelectedTemplate(e.target.value)
                }}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                disabled={isLoading}
              >
                {templates.length === 0 ? (
                  <option value="">No templates available - Create one in Configure tab</option>
                ) : (
                  templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))
                )}
              </select>
            </div>

            <FileUpload onFileSelect={handleFileSelect} multiple={true} maxFiles={5} />

            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-2 font-medium">
                Document Requirements:
              </p>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• PDF only</li>
                <li>• Maximum file size: 10MB per file</li>
                <li>• Upload 1-5 documents at once</li>
              </ul>
            </div>

            <button
              onClick={handleUploadAndExtract}
              disabled={
                !files || files.length === 0 ||
                !selectedTemplate ||
                isLoading
              }
              className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-lg"
            >
              <UploadIcon className="w-5 h-5" />
              {isLoading ? 'Processing...' : `Upload & Extract${files.length > 0 ? ` (${files.length})` : ''}`}
            </button>

            {errorMessage && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-red-900 mb-3">Extraction Failed</h3>
                    <div className="text-sm text-red-800 space-y-3">
                      {errorMessage.split('\n\n').map((section, idx) => {
                        const lines = section.split('\n').filter(line => line.trim())
                        if (lines.length === 0) return null

                        const header = lines[0]
                        const items = lines.slice(1)

                        return (
                          <div key={idx}>
                            <p className="font-medium mb-1">{header}</p>
                            {items.length > 0 && (
                              <ul className="space-y-1 ml-0">
                                {items.map((item, i) => (
                                  <li key={i}>{item}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  <button
                    onClick={() => setErrorMessage(null)}
                    className="text-red-400 hover:text-red-600 flex-shrink-0"
                  >
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}

            {batchJobs.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-800">
                    Processing Documents ({batchJobs.filter(j => j.status === 'completed').length}/{batchJobs.length} completed)
                  </h3>
                  {batchJobs.filter(j => j.status === 'completed').length > 1 && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleBatchExportJSON}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                        title="Export all results as single JSON file"
                      >
                        <Download className="w-4 h-4" />
                        Export All (JSON)
                      </button>
                      <button
                        onClick={handleBatchExportCSV}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                        title="Export all results as single CSV file"
                      >
                        <Download className="w-4 h-4" />
                        Export All (CSV)
                      </button>
                    </div>
                  )}
                </div>
                <div className="space-y-3">
                  {batchJobs.map((job, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />
                          <span className="font-medium text-gray-900 truncate">{job.filename}</span>
                        </div>
                        <div className="flex-shrink-0 ml-2">
                          {job.status === 'completed' && (
                            <CheckCircle className="w-5 h-5 text-green-600" />
                          )}
                          {job.status === 'processing' && (
                            <Loader className="w-5 h-5 text-blue-600 animate-spin" />
                          )}
                          {job.status === 'pending' && (
                            <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                          )}
                          {job.status === 'failed' && (
                            <XCircle className="w-5 h-5 text-red-600" />
                          )}
                        </div>
                      </div>

                      {job.status === 'processing' && job.jobId && (
                        <div className="mt-2">
                          <ExtractionStatus
                            jobId={job.jobId}
                            onComplete={(result) => handleBatchJobComplete(job.jobId, result)}
                            onError={(error) => handleBatchJobError(job.jobId, error)}
                            compact={true}
                          />
                        </div>
                      )}

                      {job.status === 'failed' && job.error && (
                        <div className="mt-2 text-sm text-red-600">
                          Error: {job.error}
                        </div>
                      )}

                      {job.status === 'completed' && job.extractionResult && (
                        <div className="mt-3">
                          <div className="flex items-center justify-between">
                            <div className="text-sm text-gray-600">
                              Coverage: {job.extractionResult.field_coverage_percent ? (job.extractionResult.field_coverage_percent * 100).toFixed(0) : 'N/A'}% •
                              Stage: {job.extractionResult.stage_used || 'N/A'}
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleViewResults(job)}
                                className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                title="View Results"
                              >
                                <Eye className="w-4 h-4" />
                                View
                              </button>
                              <button
                                onClick={() => handleDownloadJSON(job)}
                                className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                                title="Download JSON"
                              >
                                <FileJson className="w-4 h-4" />
                                JSON
                              </button>
                              <button
                                onClick={() => handleDownloadCSV(job)}
                                className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                                title="Download CSV"
                              >
                                <FileSpreadsheet className="w-4 h-4" />
                                CSV
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* View Results Modal */}
      {viewModalResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-gray-900">Extraction Results</h3>
                <p className="text-sm text-gray-600 mt-1">
                  Coverage: {viewModalResult.field_coverage_percent ? (viewModalResult.field_coverage_percent * 100).toFixed(0) : 'N/A'}% •
                  Stage: {viewModalResult.stage_used || 'N/A'} •
                  Time: {viewModalResult.processing_time_ms || 'N/A'}ms
                </p>
              </div>
              <button
                onClick={() => setViewModalResult(null)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title="Close"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6">
              {viewModalResult.extracted_data && Object.keys(viewModalResult.extracted_data).length > 0 ? (
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(viewModalResult.extracted_data).map(([field, value]) => (
                    <div key={field} className="border border-gray-200 p-4 rounded-lg">
                      <div className="text-xs text-gray-500 mb-2 font-medium uppercase">{field}</div>
                      <div className="text-sm text-gray-900">
                        {value !== null && value !== undefined && value !== '' ? (
                          Array.isArray(value) ? (
                            <ul className="space-y-3">
                              {value.map((item, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <span className="text-blue-600 mt-0.5">•</span>
                                  <div className="flex-1">
                                    {typeof item === 'object' && item !== null ? (
                                      <div className="bg-gray-50 rounded-md p-3 space-y-1">
                                        {Object.entries(item).map(([key, val]) => (
                                          <div key={key} className="flex items-start gap-2">
                                            <span className="text-xs font-semibold text-gray-600 uppercase min-w-[120px]">
                                              {key.replace(/_/g, ' ')}:
                                            </span>
                                            <span className="text-sm text-gray-900 flex-1">
                                              {val !== null && val !== undefined ? String(val) : '-'}
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="font-medium">{String(item)}</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="font-medium">{String(value)}</span>
                          )
                        ) : (
                          <span className="text-red-500 flex items-center gap-1">
                            <AlertCircle className="w-4 h-4" />
                            Not found
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  <p>No extraction data available</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadPage

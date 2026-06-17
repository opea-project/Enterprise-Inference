import { useState, useEffect } from 'react'
import { FileText, Eye, Download, RefreshCw, Trash2, FileJson, FileSpreadsheet, CheckSquare, Square, Archive, X, AlertCircle, Clock, CheckCircle, XCircle } from 'lucide-react'
import { getExtractionHistory, getTemplates, deleteExtraction, reExtract, getExtractionResult } from '../services/api'

const HistoryPage = () => {
  const [history, setHistory] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedItems, setSelectedItems] = useState([])
  const [showResultsModal, setShowResultsModal] = useState(false)
  const [selectedResult, setSelectedResult] = useState(null)
  const [pollingJobs, setPollingJobs] = useState(new Set())
  const [filters, setFilters] = useState({
    template_id: '',
    status: '',
    limit: 50
  })

  useEffect(() => {
    loadTemplates()
    loadHistory()

    // Auto-refresh every 3 seconds to poll for running jobs
    const interval = setInterval(() => {
      if (history.some(item => item.status === 'running' || item.status === 'pending')) {
        loadHistory()
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [filters])

  const loadTemplates = async () => {
    try {
      const data = await getTemplates()
      setTemplates(data)
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const loadHistory = async () => {
    setLoading(true)
    try {
      const data = await getExtractionHistory(filters)
      setHistory(data)
    } catch (error) {
      console.error('Failed to load history:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectItem = (id) => {
    setSelectedItems(prev =>
      prev.includes(id)
        ? prev.filter(item => item !== id)
        : [...prev, id]
    )
  }

  const handleSelectAll = () => {
    if (selectedItems.length === history.length) {
      setSelectedItems([])
    } else {
      setSelectedItems(history.map(item => item.id))
    }
  }

  const handleViewResults = (item) => {
    setSelectedResult(item)
    setShowResultsModal(true)
  }

  const handleDownloadJSON = (item) => {
    const dataStr = JSON.stringify(item.extracted_data, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${item.document_filename.replace('.pdf', '')}_extraction.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadCSV = (item) => {
    if (!item.extracted_data) return

    const headers = Object.keys(item.extracted_data)
    const values = Object.values(item.extracted_data).map(v => {
      if (v === null || v === undefined) return ''
      if (Array.isArray(v) || typeof v === 'object') {
        // Serialize arrays/objects as JSON
        return JSON.stringify(v)
      }
      return String(v)
    })
    const csv = `${headers.join(',')}\n${values.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')}`

    const dataBlob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${item.document_filename.replace('.pdf', '')}_extraction.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleReExtract = async (item) => {
    try {
      const newJob = await reExtract(item.id)
      alert(`✅ Re-extraction started! Job ID: ${newJob.id.substring(0, 8)}...`)
      loadHistory()
    } catch (error) {
      console.error('Failed to re-extract:', error)
      alert(`❌ Re-extraction failed: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this extraction result?')) return

    try {
      await deleteExtraction(id)
      loadHistory()
      setSelectedItems(prev => prev.filter(item => item !== id))
    } catch (error) {
      console.error('Failed to delete:', error)
      alert(`Failed to delete: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedItems.length === 0) return
    if (!window.confirm(`Delete ${selectedItems.length} selected items?`)) return

    try {
      await Promise.all(selectedItems.map(id => deleteExtraction(id)))
      loadHistory()
      setSelectedItems([])
    } catch (error) {
      console.error('Failed to bulk delete:', error)
      alert('Failed to delete some items')
    }
  }

  const handleBulkExportJSON = () => {
    if (selectedItems.length === 0) return

    const selectedData = history.filter(item => selectedItems.includes(item.id))
    const exportData = selectedData.map(item => ({
      filename: item.document_filename,
      template: item.template_name,
      extracted_data: item.extracted_data,
      metadata: {
        status: item.status,
        coverage: item.field_coverage_percent,
        processing_time_ms: item.processing_time_ms,
        created_at: item.created_at
      }
    }))

    const dataStr = JSON.stringify(exportData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `bulk_export_${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />
      case 'running':
        return <Clock className="w-5 h-5 text-blue-600 animate-spin" />
      case 'pending':
        return <Clock className="w-5 h-5 text-gray-400" />
      default:
        return <AlertCircle className="w-5 h-5 text-gray-400" />
    }
  }

  const getStatusBadge = (status) => {
    const colors = {
      success: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-blue-100 text-blue-800',
      pending: 'bg-gray-100 text-gray-800'
    }
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || colors.pending}`}>
        {status}
      </span>
    )
  }

  const getStageBadge = (stage) => {
    const colors = {
      traditional: 'bg-purple-100 text-purple-800',
      vision: 'bg-indigo-100 text-indigo-800',
      mock: 'bg-gray-100 text-gray-800'
    }
    return stage ? (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[stage] || colors.mock}`}>
        {stage}
      </span>
    ) : null
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Extraction History</h1>
        <p className="text-gray-600">View, manage, and export document extraction results</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Template
            </label>
            <select
              value={filters.template_id}
              onChange={(e) => setFilters({ ...filters, template_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Templates</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Status</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
              <option value="pending">Pending</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Results Per Page
            </label>
            <select
              value={filters.limit}
              onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedItems.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-blue-900">
            <CheckSquare className="w-5 h-5" />
            <span className="font-medium">{selectedItems.length} items selected</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleBulkExportJSON}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <Archive className="w-4 h-4" />
              Export Selected (JSON)
            </button>
            <button
              onClick={handleBulkDelete}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md flex items-center gap-2 text-sm"
            >
              <Trash2 className="w-4 h-4" />
              Delete Selected
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading history...</p>
        </div>
      ) : history.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md p-12 text-center">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600">No extraction history found</p>
          <p className="text-sm text-gray-500 mt-2">Run your first extraction to see results here</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          {/* Table Header */}
          <div className="bg-gray-50 px-6 py-3 border-b border-gray-200">
            <div className="grid grid-cols-12 gap-4 items-center text-xs font-medium text-gray-500 uppercase tracking-wider">
              <div className="col-span-1 flex items-center">
                <button
                  onClick={handleSelectAll}
                  className="text-gray-600 hover:text-gray-900"
                >
                  {selectedItems.length === history.length ? (
                    <CheckSquare className="w-5 h-5" />
                  ) : (
                    <Square className="w-5 h-5" />
                  )}
                </button>
              </div>
              <div className="col-span-3">Document</div>
              <div className="col-span-2">Template</div>
              <div className="col-span-1">Status</div>
              <div className="col-span-1">Coverage</div>
              <div className="col-span-2">Created</div>
              <div className="col-span-2">Actions</div>
            </div>
          </div>

          {/* Table Body */}
          <div className="divide-y divide-gray-200">
            {history.map((item) => (
              <div
                key={item.id}
                className={`px-6 py-4 hover:bg-gray-50 transition-colors ${
                  selectedItems.includes(item.id) ? 'bg-blue-50' : ''
                }`}
              >
                <div className="grid grid-cols-12 gap-4 items-center">
                  {/* Checkbox */}
                  <div className="col-span-1">
                    <button
                      onClick={() => handleSelectItem(item.id)}
                      className="text-gray-600 hover:text-gray-900"
                    >
                      {selectedItems.includes(item.id) ? (
                        <CheckSquare className="w-5 h-5 text-blue-600" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>
                  </div>

                  {/* Document */}
                  <div className="col-span-3">
                    <div className="flex items-start gap-3">
                      <FileText className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="font-medium text-gray-900 text-sm">
                          {item.document_filename || 'Unknown'}
                        </div>
                        {item.document_page_count && (
                          <div className="text-xs text-gray-500">
                            {item.document_page_count} pages
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Template */}
                  <div className="col-span-2">
                    <div className="text-sm text-gray-900">{item.template_name || 'N/A'}</div>
                    {item.stage_used && (
                      <div className="mt-1">{getStageBadge(item.stage_used)}</div>
                    )}
                  </div>

                  {/* Status */}
                  <div className="col-span-1">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(item.status)}
                    </div>
                  </div>

                  {/* Coverage */}
                  <div className="col-span-1">
                    {item.field_coverage_percent !== null && item.field_coverage_percent !== undefined ? (
                      <div className="text-sm">
                        <div className="font-medium text-gray-900">
                          {(item.field_coverage_percent * 100).toFixed(0)}%
                        </div>
                        {item.processing_time_ms && (
                          <div className="text-xs text-gray-500">
                            {item.processing_time_ms}ms
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-400 text-sm">-</span>
                    )}
                  </div>

                  {/* Created */}
                  <div className="col-span-2">
                    <div className="text-sm text-gray-900">
                      {new Date(item.created_at).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(item.created_at).toLocaleTimeString()}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="col-span-2">
                    <div className="flex items-center gap-2">
                      {item.status === 'success' && item.extracted_data && (
                        <>
                          <button
                            onClick={() => handleViewResults(item)}
                            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                            title="View Results"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDownloadJSON(item)}
                            className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                            title="Download JSON"
                          >
                            <FileJson className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDownloadCSV(item)}
                            className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                            title="Download CSV"
                          >
                            <FileSpreadsheet className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      {(item.status === 'success' || item.status === 'failed') && (
                        <button
                          onClick={() => handleReExtract(item)}
                          className="p-1.5 text-purple-600 hover:bg-purple-50 rounded transition-colors"
                          title="Re-extract"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Error message row */}
                {item.status === 'failed' && item.error_message && (
                  <div className="mt-3 ml-9 bg-red-50 border border-red-200 rounded-md p-3">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                      <div className="text-sm text-red-800">{item.error_message}</div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* View Results Modal */}
      {showResultsModal && selectedResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto m-4">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-gray-900">Extraction Results</h3>
                <p className="text-sm text-gray-600 mt-1">
                  {selectedResult.document_filename} • {selectedResult.template_name}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  {getStatusBadge(selectedResult.status)}
                  {selectedResult.stage_used && getStageBadge(selectedResult.stage_used)}
                  {selectedResult.field_coverage_percent !== null && (
                    <span className="text-sm text-gray-600">
                      Coverage: {(selectedResult.field_coverage_percent * 100).toFixed(0)}%
                    </span>
                  )}
                  {selectedResult.processing_time_ms && (
                    <span className="text-sm text-gray-600">
                      Time: {selectedResult.processing_time_ms}ms
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setShowResultsModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(selectedResult.extracted_data || {}).map(([field, value]) => (
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default HistoryPage

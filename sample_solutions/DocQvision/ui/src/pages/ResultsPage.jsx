import { useLocation, useNavigate } from 'react-router-dom'
import { Download, FileJson, FileSpreadsheet, Upload } from 'lucide-react'

const ResultsPage = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location.state?.result

  if (!result) {
    return (
      <div className="max-w-3xl mx-auto text-center py-12">
        <p className="text-gray-600 mb-4">No extraction results available</p>
        <button onClick={() => navigate('/upload')} className="btn-primary">
          Upload Document
        </button>
      </div>
    )
  }

  const { extracted_data, processing_time_ms } = result

  const handleExportJSON = () => {
    const dataStr = JSON.stringify(extracted_data, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'extracted_data.json'
    link.click()
  }

  const handleExportCSV = () => {
    const headers = Object.keys(extracted_data).filter(
      (key) => typeof extracted_data[key] !== 'object'
    )
    const values = headers.map((key) => extracted_data[key])

    const csvContent = [
      headers.join(','),
      values.map((v) => `"${v}"`).join(','),
    ].join('\n')

    const dataBlob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'extracted_data.csv'
    link.click()
  }

  const renderValue = (value) => {
    if (Array.isArray(value)) {
      return (
        <div className="space-y-2">
          {value.map((item, idx) => (
            <div key={idx} className="bg-gray-50 p-2 rounded text-sm">
              {JSON.stringify(item, null, 2)}
            </div>
          ))}
        </div>
      )
    }
    if (typeof value === 'object') {
      return <pre className="text-sm">{JSON.stringify(value, null, 2)}</pre>
    }
    return value
  }

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between mb-6 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Extraction Complete</h1>
          <p className="text-gray-600 mt-1">
            Processed in {processing_time_ms}ms
          </p>
        </div>
      </div>

      <div className="card flex-1 flex flex-col min-h-0">
        <h2 className="text-xl font-semibold text-gray-800 mb-4 flex-shrink-0">
          Extracted Data
        </h2>
        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Field Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Extracted Value
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {Object.entries(extracted_data).map(([field, value]) => (
                <tr key={field}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {field}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    {renderValue(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex gap-4 justify-between mt-6 flex-shrink-0">
        <button
          onClick={() => navigate('/upload')}
          className="btn-secondary flex items-center gap-2"
        >
          <Upload className="w-4 h-4" />
          New Document
        </button>
        <div className="flex gap-4">
          <button
            onClick={handleExportJSON}
            className="btn-secondary flex items-center gap-2"
          >
            <FileJson className="w-4 h-4" />
            Export JSON
          </button>
          <button
            onClick={handleExportCSV}
            className="btn-primary flex items-center gap-2"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>
    </div>
  )
}

export default ResultsPage

import { useState, useEffect } from 'react'
import { Loader, CheckCircle, XCircle, Clock } from 'lucide-react'
import { getExtractionResult } from '../services/api'

const ExtractionStatus = ({ jobId, onComplete, onError, compact = false }) => {
  const [status, setStatus] = useState('pending')
  const [result, setResult] = useState(null)
  const [progress, setProgress] = useState(0)
  const [startTime] = useState(Date.now())
  const [, setTick] = useState(0) // Force re-render for elapsed time display

  useEffect(() => {
    if (!jobId) return

    const pollInterval = setInterval(async () => {
      try {
        const data = await getExtractionResult(jobId)
        setStatus(data.status)

        if (data.status === 'success') {
          setProgress(100)
          setResult(data)
          clearInterval(pollInterval)
          onComplete?.(data)
        } else if (data.status === 'failed') {
          clearInterval(pollInterval)
          onError?.(data.error_message || 'Extraction failed')
        } else if (data.status === 'running') {
          // Slow, realistic progress for Xeon machine (30-75 seconds per page)
          // Expected total time: 60-180 seconds for typical 2-3 page documents
          const elapsedSeconds = (Date.now() - startTime) / 1000

          // Logarithmic progress curve - slower as it approaches completion
          // Designed for 60-180 second processing time
          let calculatedProgress = 0
          if (elapsedSeconds < 30) {
            // First 30 seconds: 0% -> 20% (fast initial progress)
            calculatedProgress = (elapsedSeconds / 30) * 20
          } else if (elapsedSeconds < 60) {
            // 30-60 seconds: 20% -> 40%
            calculatedProgress = 20 + ((elapsedSeconds - 30) / 30) * 20
          } else if (elapsedSeconds < 120) {
            // 60-120 seconds: 40% -> 65%
            calculatedProgress = 40 + ((elapsedSeconds - 60) / 60) * 25
          } else if (elapsedSeconds < 180) {
            // 120-180 seconds: 65% -> 80%
            calculatedProgress = 65 + ((elapsedSeconds - 120) / 60) * 15
          } else {
            // After 180 seconds: cap at 85% (never reach 100% until backend confirms)
            calculatedProgress = 80 + Math.min((elapsedSeconds - 180) / 60 * 5, 5)
          }

          setProgress(Math.min(Math.floor(calculatedProgress), 85))
        }
      } catch (error) {
        console.error('Polling error:', error)
        clearInterval(pollInterval)
        onError?.(error.message)
      }
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [jobId, onComplete, onError, startTime])

  // Update elapsed time display every second when processing
  useEffect(() => {
    if (status !== 'running') return

    const tickInterval = setInterval(() => {
      setTick(t => t + 1) // Force re-render to update elapsed time
    }, 1000)

    return () => clearInterval(tickInterval)
  }, [status])

  const getStatusIcon = () => {
    const iconClass = "w-6 h-6"
    switch (status) {
      case 'success':
        return <CheckCircle className={`${iconClass} text-green-600`} />
      case 'failed':
        return <XCircle className={`${iconClass} text-red-600`} />
      case 'running':
        return <Loader className={`${iconClass} text-blue-600 animate-spin`} />
      default:
        return <Clock className={`${iconClass} text-gray-600`} />
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'success': return 'text-green-600'
      case 'failed': return 'text-red-600'
      case 'running': return 'text-blue-600'
      default: return 'text-gray-600'
    }
  }

  if (compact) {
    const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000)
    const minutes = Math.floor(elapsedSeconds / 60)
    const seconds = elapsedSeconds % 60
    const timeDisplay = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`

    return (
      <div className="text-sm text-gray-600">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="capitalize">{status}</span>
          {status === 'running' && (
            <span className="text-xs text-gray-500">({timeDisplay} elapsed)</span>
          )}
        </div>
        {status === 'running' && (
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Processing on inference server... {progress}%
            </p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center gap-3 mb-4">
        {getStatusIcon()}
        <div>
          <h3 className={`text-lg font-semibold capitalize ${getStatusColor()}`}>{status}</h3>
          <p className="text-sm text-gray-600">Job ID: {jobId}</p>
        </div>
      </div>

      {status === 'running' && (
        <div className="mb-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between mt-2">
            <p className="text-sm text-gray-600">
              Processing on inference server... {progress}%
            </p>
            <p className="text-xs text-gray-500">
              {(() => {
                const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000)
                const minutes = Math.floor(elapsedSeconds / 60)
                const seconds = elapsedSeconds % 60
                return minutes > 0 ? `${minutes}m ${seconds}s elapsed` : `${seconds}s elapsed`
              })()}
            </p>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Note: Processing may take 1-3 minutes depending on document complexity
          </p>
        </div>
      )}

      {result && result.status === 'success' && (
        <div className="border-t pt-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Stage Used:</span>
              <span className="ml-2 font-medium capitalize">{result.stage_used}</span>
            </div>
            <div>
              <span className="text-gray-600">Coverage:</span>
              <span className="ml-2 font-medium">
                {result.field_coverage_percent
                  ? `${(result.field_coverage_percent * 100).toFixed(1)}%`
                  : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Processing Time:</span>
              <span className="ml-2 font-medium">
                {result.processing_time_ms ? `${result.processing_time_ms}ms` : 'N/A'}
              </span>
            </div>
            {result.model_used && (
              <div>
                <span className="text-gray-600">Model:</span>
                <span className="ml-2 font-medium">{result.model_used}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ExtractionStatus

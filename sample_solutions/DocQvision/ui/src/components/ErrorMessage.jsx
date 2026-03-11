import { AlertCircle, X } from 'lucide-react'

const ErrorMessage = ({ message, onClose, type = 'error' }) => {
  if (!message) return null

  const styles = {
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    success: 'bg-green-50 border-green-200 text-green-800'
  }

  const iconColors = {
    error: 'text-red-600',
    warning: 'text-amber-600',
    info: 'text-blue-600',
    success: 'text-green-600'
  }

  return (
    <div className={`${styles[type]} border rounded-lg p-4 mb-4 flex items-start gap-3`}>
      <AlertCircle className={`w-5 h-5 ${iconColors[type]} flex-shrink-0 mt-0.5`} />
      <div className="flex-1">
        <p className="text-sm font-medium">{message}</p>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className={`${iconColors[type]} hover:opacity-70 flex-shrink-0`}
          aria-label="Close error message"
        >
          <X className="w-5 h-5" />
        </button>
      )}
    </div>
  )
}

export default ErrorMessage

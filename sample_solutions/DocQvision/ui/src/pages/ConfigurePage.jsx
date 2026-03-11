import { useState, useEffect } from 'react'
import { Upload, Save, PlayCircle, RefreshCw, X, AlertCircle } from 'lucide-react'
import PDFPreview from '../components/PDFPreview'
import ChatInterface from '../components/ChatInterface'
import ErrorMessage from '../components/ErrorMessage'
import { configureSchema, saveTemplate, uploadDocument, createTemplate, extractData, getExtractionResult, deleteTemplate } from '../services/api'

const ConfigurePage = () => {
  const [file, setFile] = useState(null)
  const [chatHistory, setChatHistory] = useState([])
  const [schema, setSchema] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [testResults, setTestResults] = useState(null)
  const [testingStatus, setTestingStatus] = useState('')
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  useEffect(() => {
    // Load saved session from localStorage
    const savedSession = localStorage.getItem('configure_session')
    if (savedSession) {
      try {
        const { sessionId: savedSessionId, schema: savedSchema, chatHistory: savedHistory } = JSON.parse(savedSession)

        // If there's a saved session with fields, ask user if they want to continue or start fresh
        if (savedSchema && Object.keys(savedSchema).length > 0) {
          const continueSession = window.confirm(
            `📋 Previous session found with ${Object.keys(savedSchema).length} configured fields.\n\n` +
            `Do you want to continue where you left off?\n\n` +
            `Click "OK" to continue, or "Cancel" to start a new template.`
          )

          if (!continueSession) {
            localStorage.removeItem('configure_session')
            const newSessionId = crypto.randomUUID()
            setSessionId(newSessionId)
            return
          }
        }

        setSessionId(savedSessionId)
        setSchema(savedSchema || {})
        setChatHistory(savedHistory || [])
      } catch (e) {
        console.error('Failed to load saved session:', e)
        localStorage.removeItem('configure_session')
        const newSessionId = crypto.randomUUID()
        setSessionId(newSessionId)
      }
    } else {
      const newSessionId = crypto.randomUUID()
      setSessionId(newSessionId)
    }
  }, [])

  useEffect(() => {
    // Save session to localStorage whenever it changes
    if (sessionId) {
      localStorage.setItem('configure_session', JSON.stringify({
        sessionId,
        schema,
        chatHistory
      }))
    }
  }, [sessionId, schema, chatHistory])

  const handleFileUpload = (e) => {
    // Clear previous errors
    setError(null)
    setSuccessMessage(null)

    // Prevent changing PDF if session has schema configured
    if (Object.keys(schema).length > 0 && file) {
      const confirm = window.confirm(
        '⚠️ Uploading a new PDF will require starting a new session.\n\n' +
        'Your current schema configuration will be cleared.\n\n' +
        'Click "New Template" to start fresh, or cancel to keep current session.'
      )
      if (!confirm) {
        e.target.value = '' // Reset file input
        return
      }
      // User confirmed - clear session
      handleNewTemplate()
      return
    }

    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.type === 'application/pdf') {
      if (selectedFile.size <= 10 * 1024 * 1024) {
        setFile(selectedFile)
      } else {
        setError('File size must be less than 10MB')
        e.target.value = ''
      }
    } else {
      setError('Please upload a PDF file')
      e.target.value = ''
    }
  }

  const handleSendMessage = async (message) => {
    // Add user message immediately to chat history
    const userMessage = { role: 'user', content: message }
    setChatHistory(prev => [...prev, userMessage])

    setIsLoading(true)
    try {
      const response = await configureSchema(message, sessionId)
      setChatHistory(response.chat_history || [])
      setSchema(response.schema || {})
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      setError('Failed to process message')
      // Remove the user message if API call failed
      setChatHistory(prev => prev.filter(msg => msg !== userMessage))
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewTemplate = () => {
    if (Object.keys(schema).length > 0) {
      const confirm = window.confirm('This will clear your current configuration. Continue?')
      if (!confirm) return
    }
    const newSessionId = crypto.randomUUID()
    setSessionId(newSessionId)
    setSchema({})
    setChatHistory([])
    setFile(null)
    setTestResults(null)
    localStorage.removeItem('configure_session')
  }

  const handleTestExtraction = async () => {
    if (!file) {
      setError('Please upload a document first')
      return
    }
    if (Object.keys(schema).length === 0) {
      setError('Please configure extraction fields first')
      return
    }

    setIsLoading(true)
    setTestResults(null)
    let tempTemplateId = null

    try {
      // 1. Upload the document
      setTestingStatus('Uploading document...')
      const uploadResponse = await uploadDocument(file)
      const documentId = uploadResponse.document_id

      // 2. Create a temporary template
      setTestingStatus('Creating temporary template...')

      // Convert schema to proper FieldSchema format
      const convertToFieldSchema = (fieldValue) => {
        // If it's already a proper object with 'type' field
        if (typeof fieldValue === 'object' && fieldValue !== null && 'type' in fieldValue) {
          const result = {
            type: fieldValue.type,
            required: fieldValue.required !== undefined ? fieldValue.required : true
          }
          // Only add description if it exists and is not empty
          if (fieldValue.description && fieldValue.description.trim()) {
            result.description = fieldValue.description
          }
          return result
        }
        // If it's a simple string type
        if (typeof fieldValue === 'string') {
          return { type: fieldValue, required: true }
        }
        // Fallback to string
        return { type: 'string', required: true }
      }

      const tempTemplate = await createTemplate({
        name: `Test_${Date.now()}`,
        doc_type: 'test',
        schema_json: Object.fromEntries(
          Object.entries(schema).map(([field, fieldValue]) => [
            field,
            convertToFieldSchema(fieldValue)
          ])
        )
      })
      tempTemplateId = tempTemplate.id

      // 3. Run extraction
      setTestingStatus('Running extraction...')
      const extractionJob = await extractData(documentId, tempTemplateId)

      // 4. Poll for results
      let attempts = 0
      const maxAttempts = 30
      while (attempts < maxAttempts) {
        const progress = Math.round(((attempts + 1) / maxAttempts) * 100)
        setTestingStatus(`Processing extraction... ${progress}%`)
        await new Promise(resolve => setTimeout(resolve, 2000))
        const result = await getExtractionResult(extractionJob.id)

        if (result.status === 'success') {
          setTestResults(result)
          break
        } else if (result.status === 'failed') {
          setError(`Extraction Failed: ${result.error_message || 'Unknown error'}`)
          break
        }

        attempts++
      }

      if (attempts >= maxAttempts) {
        setError('Test extraction timed out. Please try again.')
      }

    } catch (error) {
      console.error('Error testing extraction:', error)
      setError(`Failed to test extraction: ${error.message}`)
    } finally {
      // Clean up: Delete the temporary template
      if (tempTemplateId) {
        try {
          setTestingStatus('Cleaning up...')
          await deleteTemplate(tempTemplateId)
        } catch (err) {
          console.error('Failed to delete temporary template:', err)
        }
      }
      setTestingStatus('')
      setIsLoading(false)
    }
  }

  const handleSaveTemplate = async () => {
    if (Object.keys(schema).length === 0) {
      setError('Please configure extraction fields first')
      return
    }

    const templateName = prompt('Enter template name:')
    if (!templateName || !templateName.trim()) {
      setError('Template name is required. Please provide a name for your template.')
      return
    }

    const templateType = prompt('Enter document type (e.g., invoice, prescription, contract):')
    if (!templateType || !templateType.trim()) {
      setError('Document type is required. This helps validate documents during extraction.')
      return
    }

    setIsLoading(true)
    try {
      // Check for duplicate template names
      const { getTemplates } = await import('../services/api')
      const existingTemplates = await getTemplates()
      const templateList = Array.isArray(existingTemplates) ? existingTemplates : (existingTemplates.templates || [])

      const duplicate = templateList.find(t => t.name.toLowerCase() === templateName.trim().toLowerCase())
      if (duplicate) {
        const overwrite = window.confirm(
          `⚠️ Template "${templateName}" already exists!\n\n` +
          `Do you want to overwrite it?`
        )
        if (!overwrite) {
          setIsLoading(false)
          return
        }
      }

      await saveTemplate(templateName.trim(), templateType.trim(), schema)
      setSuccessMessage('Template saved successfully!')
      localStorage.removeItem('configure_session') // Clear session after successful save
    } catch (error) {
      console.error('Error saving template:', error)
      if (error.response?.data?.detail) {
        setError(`Failed to save template: ${error.response.data.detail}`)
      } else {
        setError('Failed to save template. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="pb-8 flex flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Configure Document Type</h1>
          <p className="text-gray-600 mt-2">
            Upload a sample document and chat with AI to define extraction fields
          </p>
          {Object.keys(schema).length > 0 && (
            <div className="mt-2 flex items-center gap-2 text-sm text-amber-600 bg-amber-50 px-3 py-1 rounded-lg inline-flex">
              <AlertCircle className="w-4 h-4" />
              Active session with {Object.keys(schema).length} configured fields
            </div>
          )}
        </div>
        <button
          onClick={handleNewTemplate}
          className="btn-secondary flex items-center gap-2"
          title="Start a new template configuration"
        >
          <RefreshCw className="w-4 h-4" />
          New Template
        </button>
      </div>

      {/* Error Messages */}
      <ErrorMessage message={error} type="error" onClose={() => setError(null)} />
      <ErrorMessage message={successMessage} type="success" onClose={() => setSuccessMessage(null)} />

      <div className="grid grid-cols-2 gap-6">
        <div className="card flex flex-col">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-semibold text-gray-800">Document Preview</h2>
              <label className="btn-secondary cursor-pointer flex items-center gap-2">
                <Upload className="w-4 h-4" />
                Upload PDF
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
            <p className="text-xs text-gray-500">Supports PDF up to 10MB</p>
          </div>
          <div className="h-[600px]">
            <PDFPreview file={file} />
          </div>
        </div>

        <div className="card flex flex-col">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Chat</h2>
          <div className="h-[600px] border border-gray-200 rounded-lg overflow-hidden flex flex-col">
            <ChatInterface
              onSendMessage={handleSendMessage}
              chatHistory={chatHistory}
              isLoading={isLoading}
            />
          </div>
        </div>
      </div>

      {Object.keys(schema).length > 0 && (
        <div className="card mt-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">
            Configured Fields ({Object.keys(schema).length})
          </h3>
          <ul className="space-y-2">
            {Object.entries(schema).map(([field, type]) => {
              const displayType = typeof type === 'string' ? type : (type?.type || 'unknown')
              return (
                <li key={field} className="flex items-start gap-3 text-sm">
                  <span className="text-green-600 mt-0.5">●</span>
                  <div className="flex-1">
                    <span className="font-semibold text-gray-900">{field}</span>
                    <span className="text-gray-500 ml-2">({displayType})</span>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* Loading modal during test extraction */}
      {isLoading && testingStatus && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4 shadow-xl">
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mb-4"></div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Testing Extraction</h3>
              <p className="text-sm text-gray-600 text-center">{testingStatus}</p>
            </div>
          </div>
        </div>
      )}

      {/* Test results section */}
      {testResults && (
        <div className="card mt-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-800">Test Extraction Results</h3>
              <p className="text-xs text-gray-500 mt-1">
                Coverage: {testResults.field_coverage_percent ? (testResults.field_coverage_percent * 100).toFixed(0) : 0}% |
                Stage: {testResults.stage_used || 'N/A'} |
                Time: {testResults.processing_time_ms || 0}ms
              </p>
            </div>
            <button
              onClick={() => setTestResults(null)}
              className="text-gray-400 hover:text-gray-600"
              title="Clear test results"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(testResults.extracted_data || {}).map(([field, value]) => (
              <div key={field} className="border border-gray-200 p-4 rounded-lg bg-gray-50">
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
                                <div className="bg-white rounded-md p-3 space-y-1 border border-gray-200">
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
      )}

      <div className="flex gap-4 justify-end mt-6">
        <button
          onClick={handleTestExtraction}
          className="btn-secondary flex items-center gap-2"
          disabled={!file || Object.keys(schema).length === 0}
          title="Test if AI can extract your configured fields from the sample document"
        >
          <PlayCircle className="w-4 h-4" />
          Test Extraction
        </button>
        <button
          onClick={handleSaveTemplate}
          className="btn-primary flex items-center gap-2"
          disabled={Object.keys(schema).length === 0}
          title="Save this configuration as a reusable template"
        >
          <Save className="w-4 h-4" />
          Save Template
        </button>
      </div>
    </div>
  )
}

export default ConfigurePage

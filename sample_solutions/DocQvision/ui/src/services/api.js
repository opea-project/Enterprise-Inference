import axios from 'axios'

// In production (Docker), nginx proxies /api to backend, so use relative path
// In development (npm run dev), directly call backend on port 5001
const API_BASE_URL = import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:5001' : '')

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const configureSchema = async (message, sessionId = null) => {
  const formData = new FormData()
  formData.append('message', message)
  if (sessionId) {
    formData.append('session_id', sessionId)
  }
  const response = await api.post('/api/configure', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const uploadDocument = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/api/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const batchUploadDocuments = async (files) => {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  const response = await api.post('/api/documents/batch-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const extractData = async (documentId, templateId) => {
  const response = await api.post('/api/extract', {
    document_id: documentId,
    template_id: templateId
  })
  return response.data
}

export const getExtractionResult = async (jobId) => {
  const response = await api.get(`/api/extract/${jobId}`)
  return response.data
}

export const saveTemplate = async (name, templateType, schema) => {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('template_type', templateType)
  formData.append('schema', JSON.stringify(schema))
  const response = await api.post('/api/templates/save', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const createTemplate = async (templateData) => {
  const response = await api.post('/api/templates', templateData)
  return response.data
}

export const getTemplate = async (templateId) => {
  const response = await api.get(`/api/templates/${templateId}`)
  return response.data
}

export const updateTemplate = async (templateId, updateData) => {
  const response = await api.put(`/api/templates/${templateId}`, updateData)
  return response.data
}

export const deleteTemplate = async (templateId) => {
  const response = await api.delete(`/api/templates/${templateId}`)
  return response.data
}

export const getExtractionHistory = async (filters = {}) => {
  const params = new URLSearchParams()
  if (filters.template_id) params.append('template_id', filters.template_id)
  if (filters.status) params.append('status', filters.status)
  if (filters.skip) params.append('skip', filters.skip)
  if (filters.limit) params.append('limit', filters.limit)

  const response = await api.get(`/api/history?${params.toString()}`)
  return response.data
}

export const getTemplates = async () => {
  const response = await api.get('/api/templates')
  return response.data
}

export const deleteExtraction = async (jobId) => {
  const response = await api.delete(`/api/extract/${jobId}`)
  return response.data
}

export const reExtract = async (jobId) => {
  const response = await api.post(`/api/extract/${jobId}/re-extract`)
  return response.data
}

export default api

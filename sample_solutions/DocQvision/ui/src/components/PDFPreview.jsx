import { useState, useRef, useEffect } from 'react'
import { FileText, ZoomIn, ZoomOut, RotateCw, AlertCircle } from 'lucide-react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

const PDFPreview = ({ file }) => {
  const [numPages, setNumPages] = useState(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [fileUrl, setFileUrl] = useState(null)
  const [scale, setScale] = useState(1.0)
  const [rotation, setRotation] = useState(0)
  const [error, setError] = useState(null)
  const containerRef = useRef(null)
  const [containerWidth, setContainerWidth] = useState(0)

  useEffect(() => {
    if (containerRef.current) {
      const updateWidth = () => {
        setContainerWidth(containerRef.current.offsetWidth - 32)
      }
      updateWidth()
      window.addEventListener('resize', updateWidth)
      return () => window.removeEventListener('resize', updateWidth)
    }
  }, [])

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages)
    setPageNumber(1)
    setError(null)
  }

  const onDocumentLoadError = (error) => {
    console.error('PDF load error:', error)
    setError('Failed to load PDF file. Please try again.')
    setNumPages(null)
  }

  useEffect(() => {
    if (file) {
      setError(null)
      const url = URL.createObjectURL(file)
      setFileUrl(url)

      return () => {
        if (url) {
          URL.revokeObjectURL(url)
        }
      }
    } else {
      setFileUrl(null)
      setNumPages(null)
      setPageNumber(1)
      setScale(1.0)
      setRotation(0)
      setError(null)
    }
  }, [file])

  const handleZoomIn = () => {
    setScale((prev) => {
      const newScale = Math.min(prev + 0.2, 3.0)
      return newScale
    })
  }

  const handleZoomOut = () => {
    setScale((prev) => {
      const newScale = Math.max(prev - 0.2, 0.5)
      return newScale
    })
  }

  const handleRotate = () => {
    setRotation((prev) => (prev + 90) % 360)
  }

  if (!file || !fileUrl) {
    return (
      <div className="h-full bg-gray-100 rounded-lg flex flex-col">
        <div className="bg-gray-800 text-white px-4 py-2 rounded-t-lg">
          <p className="text-sm font-medium">No document selected</p>
        </div>
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            <FileText className="w-24 h-24 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-400">Upload a PDF to preview</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full bg-gray-100 rounded-lg flex flex-col">
      <div className="bg-gray-800 text-white px-4 py-2 rounded-t-lg flex items-center justify-between flex-shrink-0">
        <p className="text-sm font-medium truncate flex-1">{file.name}</p>
        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={handleZoomOut}
            className="p-1 hover:bg-gray-700 rounded"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs px-2">{Math.round(scale * 100)}%</span>
          <button
            onClick={handleZoomIn}
            className="p-1 hover:bg-gray-700 rounded"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleRotate}
            className="p-1 hover:bg-gray-700 rounded ml-2"
            title="Rotate"
          >
            <RotateCw className="w-4 h-4" />
          </button>
          {numPages && (
            <span className="text-xs ml-2">
              Page {pageNumber} of {numPages}
            </span>
          )}
        </div>
      </div>
      <div ref={containerRef} className="flex-1 overflow-auto bg-gray-200 flex items-start justify-center p-4">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
            <p className="text-red-600 font-medium mb-2">{error}</p>
            <p className="text-sm text-gray-600">
              The PDF file may be corrupted or incompatible. Please try uploading a different file.
            </p>
          </div>
        ) : (
          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-800"></div>
              </div>
            }
          >
            <Page
              pageNumber={pageNumber}
              width={containerWidth * scale}
              rotate={rotation}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </Document>
        )}
      </div>
      {numPages && numPages > 1 && (
        <div className="bg-gray-800 text-white px-4 py-2 flex items-center justify-center gap-4 flex-shrink-0">
          <button
            onClick={() => setPageNumber((prev) => Math.max(1, prev - 1))}
            disabled={pageNumber <= 1}
            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={() => setPageNumber((prev) => Math.min(numPages, prev + 1))}
            disabled={pageNumber >= numPages}
            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

export default PDFPreview

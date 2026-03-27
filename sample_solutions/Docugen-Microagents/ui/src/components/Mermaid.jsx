import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

function Mermaid({ chart }) {
  const containerRef = useRef(null)

  useEffect(() => {
    // Initialize mermaid with config
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'strict',
      fontFamily: 'ui-sans-serif, system-ui, sans-serif'
    })
  }, [])

  useEffect(() => {
    if (containerRef.current && chart) {
      const renderDiagram = async () => {
        try {
          // Clear previous content
          containerRef.current.innerHTML = ''

          // Generate new ID for each render to avoid conflicts
          const newId = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

          // Render the mermaid chart
          const { svg } = await mermaid.render(newId, chart)
          containerRef.current.innerHTML = svg
        } catch (error) {
          console.error('Mermaid rendering error:', error)
          console.error('Chart content:', chart)
          containerRef.current.innerHTML = `<pre style="color: red; padding: 1rem; background: #fee; border-radius: 8px;">Error rendering diagram: ${error.message}</pre>`
        }
      }

      renderDiagram()
    }
  }, [chart])

  return <div ref={containerRef} style={{ minHeight: '200px' }} />
}

export default Mermaid

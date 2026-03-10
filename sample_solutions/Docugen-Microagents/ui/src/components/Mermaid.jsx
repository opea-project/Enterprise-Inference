import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

// Initialize mermaid with default config
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'strict',
  fontFamily: 'ui-sans-serif, system-ui, sans-serif'
})

function Mermaid({ chart }) {
  const containerRef = useRef(null)
  const idRef = useRef(`mermaid-${Math.random().toString(36).substr(2, 9)}`)

  useEffect(() => {
    if (containerRef.current && chart) {
      const renderDiagram = async () => {
        try {
          // Clear previous content
          containerRef.current.innerHTML = ''

          // Render the mermaid chart
          const { svg } = await mermaid.render(idRef.current, chart)
          containerRef.current.innerHTML = svg
        } catch (error) {
          console.error('Mermaid rendering error:', error)
          containerRef.current.innerHTML = `<pre style="color: red;">Error rendering diagram: ${error.message}</pre>`
        }
      }

      renderDiagram()
    }
  }, [chart])

  return <div ref={containerRef} />
}

export default Mermaid

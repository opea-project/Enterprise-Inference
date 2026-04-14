import { Link, useLocation } from 'react-router-dom'
import { FileSearch } from 'lucide-react'

const Layout = ({ children }) => {
  const location = useLocation()

  const navigation = [
    { name: 'Configure', href: '/' },
    { name: 'Upload', href: '/upload' },
    { name: 'History', href: '/history' },
  ]

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
        <nav className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
              <FileSearch className="w-8 h-8 text-primary-600" />
              <span className="text-xl font-bold text-gray-900">
                DocQvision
              </span>
            </Link>

            <div className="flex items-center gap-6">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`font-medium transition-colors ${
                    location.pathname === item.href
                      ? 'text-primary-600'
                      : 'text-gray-700 hover:text-primary-600'
                  }`}
                >
                  {item.name}
                </Link>
              ))}
            </div>
          </div>
        </nav>
      </header>

      <main className="flex-1 container mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {location.pathname === '/' && (
          <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-gray-700">
              <span className="font-semibold">DocQvision</span> uses AI vision models to extract structured data from PDF documents.
              Configure extraction templates once, then reuse them for processing multiple documents.
            </p>
          </div>
        )}
        {children}
      </main>
    </div>
  )
}

export default Layout

import { Link } from 'preact-router/match'

const navigation = [
  { name: 'Dashboard', path: '/' },
  { name: 'Providers', path: '/providers' },
  { name: 'API Clients', path: '/clients' },
  { name: 'Templates', path: '/templates' },
  { name: 'Billing', path: '/billing' }
]

export default function App({ children }) {
  return (
    <div class="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex justify-between h-16">
            <div class="flex">
              {/* Logo */}
              <div class="flex-shrink-0 flex items-center">
                <h1 class="text-2xl font-bold text-primary-600">LLMHub</h1>
                <span class="ml-3 text-sm text-gray-500">Management Console</span>
              </div>

              {/* Nav Links */}
              <div class="hidden sm:ml-8 sm:flex sm:space-x-8">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.path}
                    class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                    activeClassName="!border-primary-500 !text-gray-900"
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>

            {/* Right side */}
            <div class="flex items-center">
              <div class="flex items-center space-x-2">
                <div class="h-2 w-2 rounded-full bg-green-500"></div>
                <span class="text-sm text-gray-600">Online</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer class="bg-white border-t border-gray-200 mt-12">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p class="text-center text-sm text-gray-500">
            LLMHub v1.0.0 - Multi-Provider LLM Service
          </p>
        </div>
      </footer>
    </div>
  )
}

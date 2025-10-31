import { useState, useEffect } from 'preact/hooks'
import { route } from 'preact-router'
import { api } from '@/api/client'
import Modal from '@/components/Modal'
import ProtocolModal from '@/components/ProtocolModal'

export default function ProvidersView() {
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState([])
  const [error, setError] = useState(null)
  const [editingProvider, setEditingProvider] = useState(null)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [testResults, setTestResults] = useState({}) // Stores test results per provider
  const [testingProvider, setTestingProvider] = useState(null) // Track which provider is testing
  const [protocolModal, setProtocolModal] = useState({ isOpen: false, providerKey: null })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadProviders()
    // Load test results from localStorage
    try {
      const savedResults = localStorage.getItem('llmhub_provider_tests')
      if (savedResults) {
        setTestResults(JSON.parse(savedResults))
      }
    } catch (error) {
      console.error('Failed to load test results from localStorage:', error)
    }
  }, [])

  const loadProviders = async () => {
    setLoading(true)
    try {
      // Fetch providers dynamically from registry
      const data = await api.admin.getProvidersRegistry()
      setProviders(data)
      setError(null)
    } catch (error) {
      console.error('Failed to load providers:', error)
      setError('Failed to load providers. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const startEditing = (provider) => {
    setEditingProvider(provider)
    setApiKeyInput('')
  }

  const cancelEditing = () => {
    setEditingProvider(null)
    setApiKeyInput('')
  }

  const saveApiKey = async () => {
    if (!apiKeyInput.trim()) {
      alert('Please enter an API key')
      return
    }

    setSaving(true)
    try {
      await api.admin.updateProviderApiKey(editingProvider.provider_key, apiKeyInput)
      alert('API key saved successfully to database!')

      // Clear test result for this provider since key was updated
      const newResults = { ...testResults }
      delete newResults[editingProvider.provider_key]
      setTestResults(newResults)
      localStorage.setItem('llmhub_provider_tests', JSON.stringify(newResults))

      setApiKeyInput('')
      setEditingProvider(null)
      await loadProviders()
    } catch (error) {
      console.error('Failed to save API key:', error)
      alert('Failed to save API key. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const testApiKey = async (provider, apiKeyToTest = null) => {
    setTestingProvider(provider.provider_key)

    try {
      const result = await api.admin.testProviderApiKey(provider.provider_key, apiKeyToTest)
      const newResults = {
        ...testResults,
        [provider.provider_key]: result
      }
      setTestResults(newResults)
      // Save to localStorage
      localStorage.setItem('llmhub_provider_tests', JSON.stringify(newResults))
    } catch (error) {
      console.error('Failed to test API key:', error)
      const newResults = {
        ...testResults,
        [provider.provider_key]: {
          success: false,
          steps: error.steps || [],
          error: error.error || error.detail || 'API key test failed'
        }
      }
      setTestResults(newResults)
      // Save to localStorage
      localStorage.setItem('llmhub_provider_tests', JSON.stringify(newResults))
    } finally {
      setTestingProvider(null)
    }
  }

  const openProtocol = (providerKey) => {
    setProtocolModal({ isOpen: true, providerKey })
  }

  const closeProtocol = () => {
    setProtocolModal({ isOpen: false, providerKey: null })
  }

  const viewModels = (providerKey) => {
    route(`/models?provider=${providerKey}`)
  }

  if (loading) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Providers & Models</h1>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Providers & Models</h1>
        <div class="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      </div>
    )
  }

  if (providers.length === 0) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Providers & Models</h1>
        <div class="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg">
          No providers configured. Please configure provider API keys to get started.
        </div>
      </div>
    )
  }

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Providers & Models</h1>
      </div>

      {/* Providers Grid - 3 columns */}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {providers.map((provider) => (
          <div key={provider.provider_key} class="card flex flex-col">
            {/* Header */}
            <div class="flex items-start justify-between mb-2">
              <div class="flex-1">
                <h2 class="text-lg font-semibold text-gray-900">{provider.display_name}</h2>
                <p class="text-xs text-gray-500 mt-1">{provider.models.length} models</p>
              </div>
              {testResults[provider.provider_key] && testingProvider !== provider.provider_key ? (
                testResults[provider.provider_key].success ? (
                  <span class="badge badge-success">Connected</span>
                ) : (
                  <span class="badge badge-warning">Disconnected</span>
                )
              ) : provider.configured ? (
                <span class="badge badge-success">Configured</span>
              ) : (
                <span class="badge badge-warning">Not Set</span>
              )}
            </div>

            <p class="text-sm text-gray-600 mb-3 flex-grow">{provider.description}</p>

            {/* Provider Action Section */}
            <div class="border-t border-gray-200 pt-3 mt-auto">
              <div class="space-y-2">
                {provider.website_url && (
                  <a
                    href={provider.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-xs text-primary-600 hover:text-primary-700 block"
                  >
                    Visit website →
                  </a>
                )}

                {/* API Key Display */}
                <div class="mb-2">
                  <input
                    type="text"
                    value={provider.api_key_masked || 'No API key stored'}
                    readOnly
                    class="w-full px-2 py-1.5 text-xs font-mono bg-gray-50 border border-gray-200 rounded focus:outline-none"
                  />
                </div>

                {/* Action Buttons */}
                {provider.configured ? (
                  <div class="space-y-2">
                    <div class="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => startEditing(provider)}
                        class="btn btn-secondary text-sm py-1.5"
                      >
                        Update Key
                      </button>
                      <button
                        onClick={() => testApiKey(provider)}
                        disabled={testingProvider === provider.provider_key}
                        class="btn btn-primary text-sm py-1.5"
                      >
                        {testingProvider === provider.provider_key ? 'Testing...' : 'Test'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => startEditing(provider)}
                    class="btn btn-primary w-full text-sm py-1.5"
                  >
                    Add API Key
                  </button>
                )}

                {testResults[provider.provider_key] && (
                  <button
                    onClick={() => openProtocol(provider.provider_key)}
                    class="btn btn-secondary text-sm py-1.5 w-full"
                  >
                    View Protocol
                  </button>
                )}

                {/* View Models Button - only for configured providers with models */}
                {provider.configured && provider.models.length > 0 && (
                  <button
                    onClick={() => viewModels(provider.provider_key)}
                    class="btn btn-primary text-sm py-1.5 w-full"
                  >
                    View Models →
                  </button>
                )}

                {/* Inline Status Display */}
                {testingProvider === provider.provider_key && (
                  <div class="flex items-center space-x-2 text-sm text-blue-600">
                    <div class="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
                    <span>Testing connection...</span>
                  </div>
                )}

                {testResults[provider.provider_key] && testingProvider !== provider.provider_key && (
                  <div class={`text-sm ${testResults[provider.provider_key].success ? 'text-green-600' : 'text-red-600'}`}>
                    {testResults[provider.provider_key].success ? (
                      <span>✓ Connected - {testResults[provider.provider_key].models_discovered} models found</span>
                    ) : (
                      <span>✗ Failed - {testResults[provider.provider_key].error}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* API Key Modal */}
      <Modal
        isOpen={editingProvider !== null}
        onClose={cancelEditing}
        title={`${editingProvider ? editingProvider.display_name : ''} - API Key`}
        size="lg"
      >
        {editingProvider && (
          <div>
            <p class="text-sm text-gray-600 mb-4">
              Enter your API key for {editingProvider.display_name}. You can test it before saving.
            </p>
            <div class="mb-4">
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="Enter API key..."
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p class="text-xs text-gray-500 mt-2">
                The key will be stored in the database and masked after saving for security.
              </p>
            </div>

            {/* Inline test status in modal */}
            {testingProvider === editingProvider?.provider_key && (
              <div class="mb-4 flex items-center space-x-2 text-sm text-blue-600">
                <div class="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
                <span>Testing connection...</span>
              </div>
            )}

            {testResults[editingProvider?.provider_key] && testingProvider !== editingProvider?.provider_key && (
              <div class={`mb-4 text-sm ${testResults[editingProvider.provider_key].success ? 'text-green-600' : 'text-red-600'}`}>
                {testResults[editingProvider.provider_key].success ? (
                  <span>✓ Connection successful - {testResults[editingProvider.provider_key].models_discovered} models found</span>
                ) : (
                  <span>✗ Connection failed - {testResults[editingProvider.provider_key].error}</span>
                )}
              </div>
            )}

            <div class="flex justify-between space-x-3">
              <button
                onClick={cancelEditing}
                class="btn btn-secondary"
                disabled={saving || testingProvider === editingProvider?.provider_key}
              >
                Cancel
              </button>
              <div class="flex space-x-3">
                <button
                  onClick={() => testApiKey(editingProvider, apiKeyInput)}
                  class="btn btn-secondary"
                  disabled={testingProvider === editingProvider?.provider_key || saving || !apiKeyInput.trim()}
                >
                  {testingProvider === editingProvider?.provider_key ? 'Testing...' : 'Test API Key'}
                </button>
                <button
                  onClick={saveApiKey}
                  class="btn btn-primary"
                  disabled={saving || testingProvider === editingProvider?.provider_key || !apiKeyInput.trim()}
                >
                  {saving ? 'Saving...' : 'Save API Key'}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Info Section */}
      <div class="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 class="text-sm font-medium text-blue-900 mb-2">About Provider Management</h3>
        <ul class="text-sm text-blue-800 space-y-1">
          <li><strong>API Keys:</strong> Store your provider API keys here for easy management</li>
          <li><strong>Test Key:</strong> Verify your API key works and discover available models with current costs</li>
          <li><strong>Protocol:</strong> Click "View Protocol" to see detailed connection logs</li>
          <li><strong>Security:</strong> Keys are stored securely in the database and masked in the UI</li>
          <li><strong>Fallback:</strong> Environment variables are still supported if no key is stored</li>
        </ul>
      </div>

      {/* Protocol Modal */}
      {protocolModal.isOpen && protocolModal.providerKey && (
        <ProtocolModal
          isOpen={protocolModal.isOpen}
          onClose={closeProtocol}
          providerName={providers.find(p => p.provider_key === protocolModal.providerKey)?.display_name || 'Provider'}
          testResults={testResults[protocolModal.providerKey]}
        />
      )}
    </div>
  )
}

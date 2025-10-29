import { useState, useEffect } from 'preact/hooks'
import { route } from 'preact-router'
import { api } from '@/api/client'
import Modal from '@/components/Modal'
import ProtocolModal from '@/components/ProtocolModal'
import SystemMessage, { useSystemMessage } from '@/components/system_message'

export default function ProvidersManagementView() {
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState([])
  const [editingProvider, setEditingProvider] = useState(null)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [testResults, setTestResults] = useState({}) // Now stores results per provider
  const [testingProvider, setTestingProvider] = useState(null) // Track which provider is testing
  const [protocolModal, setProtocolModal] = useState({ isOpen: false, providerKey: null })
  const [saving, setSaving] = useState(false)
  const { message, type, showMessage } = useSystemMessage()

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
      const data = await api.admin.getProviders()
      setProviders(data)
    } catch (error) {
      console.error('Failed to load providers:', error)
      alert('Failed to load providers. Please try again.')
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
      alert('API key saved successfully!')

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

  const deleteApiKey = async (providerKey) => {
    if (!confirm('Are you sure you want to delete this API key?')) {
      return
    }

    try {
      await api.admin.deleteProviderApiKey(providerKey)
      alert('API key deleted successfully!')

      // Clear test result for this provider
      const newResults = { ...testResults }
      delete newResults[providerKey]
      setTestResults(newResults)
      localStorage.setItem('llmhub_provider_tests', JSON.stringify(newResults))

      await loadProviders()
    } catch (error) {
      console.error('Failed to delete API key:', error)
      alert('Failed to delete API key. Please try again.')
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

  const getCurrentStep = (steps) => {
    if (!steps || steps.length === 0) return null
    const runningStep = steps.find(s => s.status === 'running')
    if (runningStep) return runningStep
    return steps[steps.length - 1]
  }

  if (loading) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Provider Management</h1>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Provider Management</h1>
        <div class="flex-1 max-w-2xl ml-4">
          <SystemMessage type={type} message={message} />
        </div>
      </div>

      {/* Providers Grid */}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {providers.map((provider) => (
          <div key={provider.provider_id} class="card flex flex-col">
            {/* Header */}
            <div class="flex items-start justify-between mb-2">
              <div class="flex-1">
                <h2 class="text-lg font-semibold text-gray-900">{provider.display_name}</h2>
                <p class="text-xs text-gray-500 mt-1">{provider.model_count} models</p>
              </div>
              {testResults[provider.provider_key] && testingProvider !== provider.provider_key ? (
                testResults[provider.provider_key].success ? (
                  <span class="badge badge-success">Connected</span>
                ) : (
                  <span class="badge badge-warning">Disconnected</span>
                )
              ) : provider.api_key_configured ? (
                <span class="badge badge-success">Configured</span>
              ) : (
                <span class="badge badge-warning">Not Set</span>
              )}
            </div>

            <p class="text-sm text-gray-600 mb-3 flex-grow">{provider.description}</p>

            {/* API Key Section */}
            <div class="border-t border-gray-200 pt-3 mt-auto">
              {provider.api_key_masked ? (
                <div class="space-y-2">
                  <div class="flex items-center justify-between">
                    <code class="flex-1 bg-gray-100 px-2 py-1.5 rounded text-xs font-mono text-gray-800 truncate mr-2">
                      {provider.api_key_masked}
                    </code>
                    {provider.has_stored_key && (
                      <button
                        onClick={() => deleteApiKey(provider.provider_key)}
                        class="text-xs text-red-600 hover:text-red-800"
                        title="Delete Key"
                      >
                        Delete
                      </button>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div class="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => startEditing(provider)}
                      class="btn btn-secondary text-sm py-1.5"
                    >
                      Update
                    </button>
                    <button
                      onClick={() => testApiKey(provider)}
                      disabled={testingProvider === provider.provider_key}
                      class="btn btn-primary text-sm py-1.5"
                    >
                      {testingProvider === provider.provider_key ? 'Testing...' : 'Test'}
                    </button>
                  </div>

                  {testResults[provider.provider_key] && (
                    <button
                      onClick={() => openProtocol(provider.provider_key)}
                      class="btn btn-secondary text-sm py-1.5 w-full"
                    >
                      View Protocol
                    </button>
                  )}

                  {/* View Models Button */}
                  <button
                    onClick={() => viewModels(provider.provider_key)}
                    class="btn btn-primary text-sm py-1.5 w-full"
                  >
                    View Models →
                  </button>

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
              ) : (
                <div class="space-y-2">
                  <div class="bg-gray-50 px-3 py-2 rounded text-sm text-gray-500 italic text-center">
                    No API key stored
                  </div>
                  <button
                    onClick={() => startEditing(provider)}
                    class="btn btn-primary w-full"
                  >
                    Add API Key
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Edit API Key Modal */}
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
              <label class="block text-sm font-medium text-gray-700 mb-2">
                API Key
              </label>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="Enter API key..."
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p class="text-xs text-gray-500 mt-2">
                The key will be masked after saving for security.
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
          <li><strong>Protocol:</strong> Click Protocol button to see detailed connection logs</li>
          <li><strong>Security:</strong> Keys are stored securely and masked in the UI</li>
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

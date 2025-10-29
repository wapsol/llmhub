import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'
import SystemMessage, { useSystemMessage } from '@/components/system_message'

export default function APIClientsView() {
  const [loading, setLoading] = useState(true)
  const [clients, setClients] = useState([])
  const [showKeys, setShowKeys] = useState({})
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showIntegrationModal, setShowIntegrationModal] = useState(false)
  const [selectedClient, setSelectedClient] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [copyFeedback, setCopyFeedback] = useState('')
  const [newClient, setNewClient] = useState({
    client_name: '',
    organization: '',
    contact_email: '',
    rate_limit: 100,
    monthly_budget_usd: null
  })
  const [editClient, setEditClient] = useState({
    client_id: '',
    client_name: '',
    organization: '',
    contact_email: '',
    rate_limit: 100,
    monthly_budget_usd: null,
    is_active: true
  })
  const { message, type, showMessage } = useSystemMessage()

  // Get base URL from environment or default to localhost
  const BASE_URL = window.location.origin.includes('localhost')
    ? 'http://localhost:4000'
    : window.location.origin.replace(':5173', ':4000').replace(':5174', ':4000')

  const maskApiKey = (key) => {
    if (!key) return ''
    const prefix = key.substring(0, 12)
    return `${prefix}${'*'.repeat(20)}`
  }

  const toggleKeyVisibility = (clientId) => {
    setShowKeys(prev => ({ ...prev, [clientId]: !prev[clientId] }))
  }

  const copyToClipboard = async (text, label = 'Content') => {
    try {
      await navigator.clipboard.writeText(text)
      setCopyFeedback(`${label} copied!`)
      setTimeout(() => setCopyFeedback(''), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
      alert('Failed to copy to clipboard')
    }
  }

  const openIntegrationModal = (client) => {
    setSelectedClient(client)
    setShowIntegrationModal(true)
    setActiveTab('overview')
  }

  const closeIntegrationModal = () => {
    setShowIntegrationModal(false)
    setSelectedClient(null)
    setActiveTab('overview')
  }

  const copyAllEssentials = (client) => {
    const essentials = `=== LLMHub API Integration Details ===

Client: ${client.client_name}
${client.organization ? `Organization: ${client.organization}` : ''}
${client.contact_email ? `Contact: ${client.contact_email}` : ''}

API Key: ${client.api_key}
Base URL: ${BASE_URL}/api/v1
Rate Limit: ${client.rate_limit || 100} requests/min
Monthly Budget: ${formatCurrency(client.monthly_budget_usd)}

AUTHENTICATION:
Add this header to all requests:
X-API-Key: ${client.api_key}

QUICK START (cURL):
curl -X POST "${BASE_URL}/api/v1/llm/generate-content" \\
  -H "X-API-Key: ${client.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{"prompt": "Your prompt here", "provider": "claude", "max_tokens": 1000}'

PROVIDERS:
- claude (recommended): claude-3-5-sonnet-20241022, claude-3-opus-20240229, claude-3-haiku-20240307
- openai: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
- groq (cheapest/fastest): llama-3.3-70b-versatile, mixtral-8x7b-32768

ENDPOINTS:
POST ${BASE_URL}/api/v1/llm/generate-content - Generate text content
POST ${BASE_URL}/api/v1/llm/translate - Translate to multiple languages
POST ${BASE_URL}/api/v1/llm/generate-image - Generate images with DALL-E
GET  ${BASE_URL}/api/v1/llm/prompts - List available templates

Full API Documentation: ${BASE_URL}/docs
Interactive Testing: ${BASE_URL}/docs (Swagger UI)

Questions? Contact your LLMHub administrator.`

    copyToClipboard(essentials, 'All integration details')
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
  }

  const formatCurrency = (amount) => {
    if (!amount) return 'Unlimited'
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount)
  }

  const loadClients = async () => {
    try {
      const data = await api.admin.getClients()
      setClients(data)
      // Initialize show/hide state
      const keysState = {}
      data.forEach(client => {
        keysState[client.client_id] = false
      })
      setShowKeys(keysState)
    } catch (error) {
      console.error('Failed to load clients:', error)
    } finally {
      setLoading(false)
    }
  }

  const createClient = async () => {
    try {
      if (!newClient.client_name) {
        alert('Client name is required')
        return
      }
      await api.admin.createClient(newClient)
      await loadClients()
      closeCreateModal()
      alert('Client created successfully!')
    } catch (error) {
      console.error('Failed to create client:', error)
      alert('Failed to create client: ' + error.message)
    }
  }

  const regenerateKey = async (client) => {
    if (!confirm(`Regenerate API key for ${client.client_name}? The old key will be invalidated.`)) {
      return
    }
    try {
      await api.admin.regenerateKey(client.client_id)
      await loadClients()
      alert('API key regenerated successfully!')
    } catch (error) {
      console.error('Failed to regenerate key:', error)
      alert('Failed to regenerate key')
    }
  }

  const deleteClient = async (client) => {
    if (!confirm(`Delete ${client.client_name}? This action cannot be undone.`)) {
      return
    }
    try {
      await api.admin.deleteClient(client.client_id)
      await loadClients()
      alert('Client deleted successfully')
    } catch (error) {
      console.error('Failed to delete client:', error)
      alert('Failed to delete client')
    }
  }

  const closeCreateModal = () => {
    setShowCreateModal(false)
    setNewClient({
      client_name: '',
      organization: '',
      contact_email: '',
      rate_limit: 100,
      monthly_budget_usd: null
    })
  }

  const openEditModal = (client) => {
    setEditClient({
      client_id: client.client_id,
      client_name: client.client_name,
      organization: client.organization || '',
      contact_email: client.contact_email || '',
      rate_limit: client.rate_limit || 100,
      monthly_budget_usd: client.monthly_budget_usd || null,
      is_active: client.is_active
    })
    setShowEditModal(true)
  }

  const closeEditModal = () => {
    setShowEditModal(false)
    setEditClient({
      client_id: '',
      client_name: '',
      organization: '',
      contact_email: '',
      rate_limit: 100,
      monthly_budget_usd: null,
      is_active: true
    })
  }

  const updateClient = async () => {
    try {
      if (!editClient.client_name) {
        alert('Client name is required')
        return
      }
      await api.admin.updateClient(editClient.client_id, {
        client_name: editClient.client_name,
        organization: editClient.organization,
        contact_email: editClient.contact_email,
        rate_limit: editClient.rate_limit,
        monthly_budget_usd: editClient.monthly_budget_usd,
        is_active: editClient.is_active
      })
      await loadClients()
      closeEditModal()
      alert('Client updated successfully!')
    } catch (error) {
      console.error('Failed to update client:', error)
      alert('Failed to update client: ' + error.message)
    }
  }

  useEffect(() => {
    loadClients()
  }, [])

  // Handle ESC key to close modals
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        if (showIntegrationModal) {
          closeIntegrationModal()
        } else if (showCreateModal) {
          closeCreateModal()
        } else if (showEditModal) {
          closeEditModal()
        }
      }
    }

    // Add event listener if any modal is open
    if (showIntegrationModal || showCreateModal || showEditModal) {
      document.addEventListener('keydown', handleEscape)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
    }

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [showIntegrationModal, showCreateModal, showEditModal])

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">API Clients</h1>
        <div class="flex items-center space-x-2 flex-1 justify-end">
          <div class="flex-1 max-w-2xl">
            <SystemMessage type={type} message={message} />
          </div>
          <button onClick={() => setShowCreateModal(true)} class="btn-primary">
            <svg class="inline-block w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
            </svg>
            Create Client
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Clients Grid */}
      {!loading && (
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {clients.map((client) => (
            <div key={client.client_id} class="card flex flex-col">
              {/* Header */}
              <div class="flex items-start justify-between mb-3">
                <div class="flex-1">
                  <h3 class="text-lg font-semibold text-gray-900">{client.client_name}</h3>
                  {client.organization && <p class="text-sm text-gray-600 mt-1">{client.organization}</p>}
                </div>
                <span class={`badge ${client.is_active ? 'badge-success' : 'badge-danger'}`}>
                  {client.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              {client.contact_email && (
                <p class="text-sm text-gray-500 mb-4">{client.contact_email}</p>
              )}

              {/* API Key */}
              {client.api_key && (
                <div class="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <p class="text-xs font-medium text-gray-700 mb-2">API Key</p>
                  <div class="flex items-center space-x-2">
                    <code class="flex-1 text-xs font-mono text-gray-900 break-all">
                      {showKeys[client.client_id] ? client.api_key : maskApiKey(client.api_key)}
                    </code>
                    <button
                      onClick={() => toggleKeyVisibility(client.client_id)}
                      class="p-1.5 text-gray-500 hover:text-gray-700 transition-colors flex-shrink-0"
                      title={showKeys[client.client_id] ? 'Hide' : 'Show'}
                    >
                      {!showKeys[client.client_id] ? (
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                        </svg>
                      ) : (
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"></path>
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => copyToClipboard(client.api_key)}
                      class="p-1.5 text-gray-500 hover:text-gray-700 transition-colors flex-shrink-0"
                      title="Copy"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              )}

              {/* Stats */}
              <div class="grid grid-cols-2 gap-3 mb-4">
                <div class="bg-gray-50 p-3 rounded-lg">
                  <p class="text-xs text-gray-600">Rate Limit</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{client.rate_limit || 100}/min</p>
                </div>
                <div class="bg-gray-50 p-3 rounded-lg">
                  <p class="text-xs text-gray-600">Budget</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">
                    {formatCurrency(client.monthly_budget_usd)}
                  </p>
                </div>
              </div>

              <div class="text-xs text-gray-500 mb-4">
                Created: {formatDate(client.created_at)}
              </div>

              {/* Actions - at bottom */}
              <div class="mt-auto pt-4 border-t border-gray-200 flex flex-col space-y-2">
                <button onClick={() => openIntegrationModal(client)} class="btn-primary text-sm w-full">
                  <svg class="inline-block w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                  </svg>
                  Integration Guide
                </button>
                <div class="grid grid-cols-3 gap-2">
                  <button onClick={() => openEditModal(client)} class="btn-secondary text-xs">
                    Edit
                  </button>
                  <button onClick={() => regenerateKey(client)} class="btn-secondary text-xs">
                    Regenerate
                  </button>
                  <button onClick={() => deleteClient(client)} class="btn-danger text-xs">
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Empty State */}
          {clients.length === 0 && (
            <div class="card text-center py-12">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
              </svg>
              <h3 class="mt-4 text-lg font-medium text-gray-900">No API clients yet</h3>
              <p class="mt-2 text-sm text-gray-600">Get started by creating your first API client.</p>
              <button onClick={() => setShowCreateModal(true)} class="btn-primary mt-6">
                Create Client
              </button>
            </div>
          )}
        </div>
      )}

      {/* Integration Guide Modal */}
      {showIntegrationModal && selectedClient && (
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto p-4">
          <div class="bg-white rounded-lg shadow-xl max-w-5xl w-full mx-4 my-8">
            {/* Modal Header */}
            <div class="bg-primary-600 text-white px-6 py-4 rounded-t-lg flex justify-between items-center">
              <div>
                <h2 class="text-xl font-bold">Integration Guide: {selectedClient.client_name}</h2>
                <p class="text-sm text-primary-100 mt-1">Complete API documentation for your client</p>
              </div>
              <button onClick={closeIntegrationModal} class="text-white hover:text-primary-200">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>

            {/* Copy Feedback */}
            {copyFeedback && (
              <div class="bg-green-50 border-l-4 border-green-500 px-4 py-2 mx-6 mt-4">
                <p class="text-sm text-green-700 font-medium">{copyFeedback}</p>
              </div>
            )}

            {/* Tabs */}
            <div class="border-b border-gray-200 px-6">
              <div class="flex space-x-1 overflow-x-auto">
                {['overview', 'curl', 'python', 'javascript', 'go'].map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    class={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === tab
                        ? 'border-primary-600 text-primary-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab Content */}
            <div class="px-6 py-6 max-h-[70vh] overflow-y-auto">
              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <div class="space-y-6">
                  {/* Quick Reference */}
                  <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div class="flex justify-between items-start mb-3">
                      <h3 class="font-semibold text-blue-900 flex items-center">
                        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Quick Reference
                      </h3>
                      <button
                        onClick={() => copyAllEssentials(selectedClient)}
                        class="btn-primary text-xs px-4 py-2 flex items-center space-x-2"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                        </svg>
                        <span>Copy All Essentials</span>
                      </button>
                    </div>
                    <div class="space-y-3">
                      <div>
                        <label class="text-xs font-medium text-blue-900">API Key</label>
                        <div class="flex items-center space-x-2 mt-1">
                          <code class="flex-1 bg-white px-3 py-2 rounded border border-blue-300 text-sm font-mono break-all">
                            {selectedClient.api_key}
                          </code>
                          <button onClick={() => copyToClipboard(selectedClient.api_key, 'API Key')} class="btn-secondary text-xs px-3 py-2">
                            Copy
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs font-medium text-blue-900">Base URL</label>
                        <div class="flex items-center space-x-2 mt-1">
                          <code class="flex-1 bg-white px-3 py-2 rounded border border-blue-300 text-sm font-mono">
                            {BASE_URL}/api/v1
                          </code>
                          <button onClick={() => copyToClipboard(`${BASE_URL}/api/v1`, 'Base URL')} class="btn-secondary text-xs px-3 py-2">
                            Copy
                          </button>
                        </div>
                      </div>
                      <div class="grid grid-cols-2 gap-3">
                        <div>
                          <label class="text-xs font-medium text-blue-900">Rate Limit</label>
                          <div class="bg-white px-3 py-2 rounded border border-blue-300 text-sm font-medium">
                            {selectedClient.rate_limit || 100} requests/min
                          </div>
                        </div>
                        <div>
                          <label class="text-xs font-medium text-blue-900">Monthly Budget</label>
                          <div class="bg-white px-3 py-2 rounded border border-blue-300 text-sm font-medium">
                            {formatCurrency(selectedClient.monthly_budget_usd)}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Available Endpoints */}
                  <div>
                    <h3 class="font-semibold text-gray-900 mb-3">Available Endpoints</h3>
                    <div class="space-y-2">
                      <EndpointCard
                        method="POST"
                        path="/llm/generate-content"
                        description="Generate text content using any LLM provider"
                      />
                      <EndpointCard
                        method="POST"
                        path="/llm/translate"
                        description="Translate content into multiple languages"
                      />
                      <EndpointCard
                        method="POST"
                        path="/llm/generate-image"
                        description="Generate images using DALL-E"
                      />
                      <EndpointCard
                        method="GET"
                        path="/llm/prompts"
                        description="List available prompt templates"
                      />
                    </div>
                  </div>

                  {/* Provider and Model Selection */}
                  <div>
                    <h3 class="font-semibold text-gray-900 mb-3">Provider & Model Selection</h3>
                    <div class="space-y-3">
                      <ProviderCard
                        name="Claude (Anthropic)"
                        key="claude"
                        models={['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307']}
                        description="Best for complex reasoning and long context (200K tokens)"
                      />
                      <ProviderCard
                        name="OpenAI"
                        key="openai"
                        models={['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']}
                        description="Best for general tasks and image generation"
                      />
                      <ProviderCard
                        name="Groq"
                        key="groq"
                        models={['llama-3.3-70b-versatile', 'mixtral-8x7b-32768', 'llama2-70b-4096']}
                        description="Best for ultra-fast inference (much cheaper)"
                      />
                    </div>
                  </div>

                  {/* Authentication */}
                  <div>
                    <h3 class="font-semibold text-gray-900 mb-3">Authentication</h3>
                    <div class="bg-gray-50 border border-gray-200 rounded p-4">
                      <p class="text-sm text-gray-700 mb-2">Include your API key in the request header:</p>
                      <code class="block bg-gray-900 text-gray-100 px-3 py-2 rounded text-sm font-mono">
                        X-API-Key: {selectedClient.api_key}
                      </code>
                    </div>
                  </div>

                  {/* Error Codes */}
                  <div>
                    <h3 class="font-semibold text-gray-900 mb-3">Common Error Codes</h3>
                    <div class="space-y-1 text-sm">
                      <ErrorCodeRow code="401" description="Invalid or missing API key" />
                      <ErrorCodeRow code="403" description="Inactive client or budget exceeded" />
                      <ErrorCodeRow code="429" description="Rate limit exceeded" />
                      <ErrorCodeRow code="500" description="Server error or LLM provider issue" />
                    </div>
                  </div>
                </div>
              )}

              {/* cURL Tab */}
              {activeTab === 'curl' && (
                <CurlExamples client={selectedClient} baseUrl={BASE_URL} copyToClipboard={copyToClipboard} />
              )}

              {/* Python Tab */}
              {activeTab === 'python' && (
                <PythonExamples client={selectedClient} baseUrl={BASE_URL} copyToClipboard={copyToClipboard} />
              )}

              {/* JavaScript Tab */}
              {activeTab === 'javascript' && (
                <JavaScriptExamples client={selectedClient} baseUrl={BASE_URL} copyToClipboard={copyToClipboard} />
              )}

              {/* Go Tab */}
              {activeTab === 'go' && (
                <GoExamples client={selectedClient} baseUrl={BASE_URL} copyToClipboard={copyToClipboard} />
              )}
            </div>

            {/* Modal Footer */}
            <div class="bg-gray-50 px-6 py-4 rounded-b-lg flex justify-between items-center border-t border-gray-200">
              <div class="text-sm text-gray-600">
                <a href={`${BASE_URL}/docs`} target="_blank" class="text-primary-600 hover:text-primary-700 font-medium">
                  View Full API Documentation →
                </a>
              </div>
              <button onClick={closeIntegrationModal} class="btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Client Modal */}
      {showCreateModal && (
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h2 class="text-xl font-bold text-gray-900 mb-4">Create API Client</h2>

            <div class="space-y-4">
              <div>
                <label class="label">Client Name *</label>
                <input
                  value={newClient.client_name}
                  onInput={(e) => setNewClient({ ...newClient, client_name: e.target.value })}
                  type="text"
                  class="input"
                  placeholder="my-application"
                />
              </div>

              <div>
                <label class="label">Organization</label>
                <input
                  value={newClient.organization}
                  onInput={(e) => setNewClient({ ...newClient, organization: e.target.value })}
                  type="text"
                  class="input"
                  placeholder="Your Company Inc."
                />
              </div>

              <div>
                <label class="label">Contact Email</label>
                <input
                  value={newClient.contact_email}
                  onInput={(e) => setNewClient({ ...newClient, contact_email: e.target.value })}
                  type="email"
                  class="input"
                  placeholder="admin@example.com"
                />
              </div>

              <div>
                <label class="label">Rate Limit (requests/min)</label>
                <input
                  value={newClient.rate_limit}
                  onInput={(e) => setNewClient({ ...newClient, rate_limit: parseInt(e.target.value) || 100 })}
                  type="number"
                  class="input"
                  placeholder="100"
                />
              </div>

              <div>
                <label class="label">Monthly Budget (EUR)</label>
                <input
                  value={newClient.monthly_budget_usd || ''}
                  onInput={(e) => setNewClient({ ...newClient, monthly_budget_usd: parseFloat(e.target.value) || null })}
                  type="number"
                  step="0.01"
                  class="input"
                  placeholder="500,00"
                />
              </div>
            </div>

            <div class="flex justify-end space-x-3 mt-6">
              <button onClick={closeCreateModal} class="btn-secondary">Cancel</button>
              <button onClick={createClient} class="btn-primary">Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Client Modal */}
      {showEditModal && (
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h2 class="text-xl font-bold text-gray-900 mb-4">Edit API Client</h2>

            <div class="space-y-4">
              <div>
                <label class="label">Client Name *</label>
                <input
                  value={editClient.client_name}
                  onInput={(e) => setEditClient({ ...editClient, client_name: e.target.value })}
                  type="text"
                  class="input"
                  placeholder="my-application"
                />
              </div>

              <div>
                <label class="label">Organization</label>
                <input
                  value={editClient.organization}
                  onInput={(e) => setEditClient({ ...editClient, organization: e.target.value })}
                  type="text"
                  class="input"
                  placeholder="Your Company Inc."
                />
              </div>

              <div>
                <label class="label">Contact Email</label>
                <input
                  value={editClient.contact_email}
                  onInput={(e) => setEditClient({ ...editClient, contact_email: e.target.value })}
                  type="email"
                  class="input"
                  placeholder="admin@example.com"
                />
              </div>

              <div>
                <label class="label">Rate Limit (requests/min)</label>
                <input
                  value={editClient.rate_limit}
                  onInput={(e) => setEditClient({ ...editClient, rate_limit: parseInt(e.target.value) || 100 })}
                  type="number"
                  class="input"
                  placeholder="100"
                />
              </div>

              <div>
                <label class="label">Monthly Budget (EUR)</label>
                <input
                  value={editClient.monthly_budget_usd || ''}
                  onInput={(e) => setEditClient({ ...editClient, monthly_budget_usd: parseFloat(e.target.value) || null })}
                  type="number"
                  step="0.01"
                  class="input"
                  placeholder="500,00"
                />
              </div>

              <div>
                <label class="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editClient.is_active}
                    onChange={(e) => setEditClient({ ...editClient, is_active: e.target.checked })}
                    class="mr-2"
                  />
                  <span class="text-sm font-medium text-gray-700">Active</span>
                </label>
              </div>
            </div>

            <div class="flex justify-end space-x-3 mt-6">
              <button onClick={closeEditModal} class="btn-secondary">Cancel</button>
              <button onClick={updateClient} class="btn-primary">Update</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Helper Components
function EndpointCard({ method, path, description }) {
  return (
    <div class="flex items-start space-x-3 bg-gray-50 border border-gray-200 rounded p-3">
      <span class={`px-2 py-0.5 text-xs font-bold rounded ${
        method === 'POST' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
      }`}>
        {method}
      </span>
      <div class="flex-1">
        <code class="text-sm font-mono text-gray-900">{path}</code>
        <p class="text-xs text-gray-600 mt-1">{description}</p>
      </div>
    </div>
  )
}

function ProviderCard({ name, key: providerKey, models, description }) {
  return (
    <div class="bg-gray-50 border border-gray-200 rounded p-3">
      <div class="flex justify-between items-start mb-2">
        <div>
          <h4 class="font-medium text-gray-900">{name}</h4>
          <p class="text-xs text-gray-600 mt-1">{description}</p>
        </div>
        <code class="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded">{providerKey}</code>
      </div>
      <div class="mt-2">
        <p class="text-xs font-medium text-gray-700 mb-1">Available Models:</p>
        <div class="flex flex-wrap gap-1">
          {models.map(model => (
            <code key={model} class="text-xs px-2 py-0.5 bg-white border border-gray-300 text-gray-700 rounded">
              {model}
            </code>
          ))}
        </div>
      </div>
    </div>
  )
}

function ErrorCodeRow({ code, description }) {
  return (
    <div class="flex items-center space-x-3 py-2 border-b border-gray-200 last:border-0">
      <code class="px-2 py-1 bg-red-100 text-red-700 font-mono text-sm rounded">{code}</code>
      <span class="text-gray-700">{description}</span>
    </div>
  )
}

function CodeBlock({ code, language = 'bash', copyToClipboard, label = 'code' }) {
  return (
    <div class="relative">
      <pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
        <code>{code}</code>
      </pre>
      <button
        onClick={() => copyToClipboard(code, label)}
        class="absolute top-2 right-2 btn-secondary text-xs px-3 py-1"
      >
        Copy
      </button>
    </div>
  )
}

// Code Example Components
function CurlExamples({ client, baseUrl, copyToClipboard }) {
  const contentExample = `curl -X POST "${baseUrl}/api/v1/llm/generate-content" \\
  -H "X-API-Key: ${client.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "provider": "claude",
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "temperature": 0.7
  }'`

  const translateExample = `curl -X POST "${baseUrl}/api/v1/llm/translate" \\
  -H "X-API-Key: ${client.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": {
      "title": "Introduction to AI",
      "body": "Artificial intelligence is transforming..."
    },
    "source_language": "en",
    "target_languages": ["de", "fr"],
    "provider": "claude"
  }'`

  const imageExample = `curl -X POST "${baseUrl}/api/v1/llm/generate-image" \\
  -H "X-API-Key: ${client.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "A futuristic data center with glowing servers",
    "size": "1024x1024",
    "quality": "hd"
  }'`

  return (
    <div class="space-y-6">
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Generate Content</h3>
        <CodeBlock code={contentExample} copyToClipboard={copyToClipboard} label="cURL content example" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Translate Content</h3>
        <CodeBlock code={translateExample} copyToClipboard={copyToClipboard} label="cURL translate example" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Generate Image</h3>
        <CodeBlock code={imageExample} copyToClipboard={copyToClipboard} label="cURL image example" />
      </div>
    </div>
  )
}

function PythonExamples({ client, baseUrl, copyToClipboard }) {
  const setupCode = `import requests

LLMHUB_URL = "${baseUrl}/api/v1"
API_KEY = "${client.api_key}"`

  const contentExample = `def generate_content(prompt, provider="claude", model="claude-3-5-sonnet-20241022"):
    """Generate content using LLMHub"""
    response = requests.post(
        f"{LLMHUB_URL}/llm/generate-content",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "prompt": prompt,
            "provider": provider,
            "model": model,
            "max_tokens": 1000,
            "temperature": 0.7
        }
    )

    if response.status_code == 200:
        data = response.json()
        return data["content"]
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")

# Usage
content = generate_content("Explain quantum computing in simple terms")
print(content)`

  const translateExample = `def translate_content(content, source_lang, target_langs):
    """Translate content to multiple languages"""
    response = requests.post(
        f"{LLMHUB_URL}/llm/translate",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "content": content,
            "source_language": source_lang,
            "target_languages": target_langs,
            "provider": "claude"
        }
    )

    if response.status_code == 200:
        return response.json()["translations"]
    else:
        raise Exception(f"Error: {response.status_code}")

# Usage
translations = translate_content(
    {"title": "Hello", "body": "World"},
    "en",
    ["de", "fr"]
)
print(translations)`

  return (
    <div class="space-y-6">
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Setup</h3>
        <CodeBlock code={setupCode} language="python" copyToClipboard={copyToClipboard} label="Python setup" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Generate Content</h3>
        <CodeBlock code={contentExample} language="python" copyToClipboard={copyToClipboard} label="Python content example" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Translate Content</h3>
        <CodeBlock code={translateExample} language="python" copyToClipboard={copyToClipboard} label="Python translate example" />
      </div>
    </div>
  )
}

function JavaScriptExamples({ client, baseUrl, copyToClipboard }) {
  const setupCode = `const LLMHUB_URL = '${baseUrl}/api/v1';
const API_KEY = '${client.api_key}';`

  const contentExample = `async function generateContent(prompt, provider = 'claude') {
  try {
    const response = await fetch(\`\${LLMHUB_URL}/llm/generate-content\`, {
      method: 'POST',
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt: prompt,
        provider: provider,
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 1000,
        temperature: 0.7
      })
    });

    if (!response.ok) {
      throw new Error(\`HTTP error! status: \${response.status}\`);
    }

    const data = await response.json();
    return data.content;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}

// Usage
generateContent('Explain quantum computing in simple terms')
  .then(content => console.log(content))
  .catch(error => console.error(error));`

  const translateExample = `async function translateContent(content, sourceLang, targetLangs) {
  const response = await fetch(\`\${LLMHUB_URL}/llm/translate\`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      content: content,
      source_language: sourceLang,
      target_languages: targetLangs,
      provider: 'claude'
    })
  });

  const data = await response.json();
  return data.translations;
}

// Usage
const translations = await translateContent(
  { title: 'Hello', body: 'World' },
  'en',
  ['de', 'fr']
);`

  return (
    <div class="space-y-6">
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Setup</h3>
        <CodeBlock code={setupCode} language="javascript" copyToClipboard={copyToClipboard} label="JavaScript setup" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Generate Content</h3>
        <CodeBlock code={contentExample} language="javascript" copyToClipboard={copyToClipboard} label="JavaScript content example" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Translate Content</h3>
        <CodeBlock code={translateExample} language="javascript" copyToClipboard={copyToClipboard} label="JavaScript translate example" />
      </div>
    </div>
  )
}

function GoExamples({ client, baseUrl, copyToClipboard }) {
  const setupCode = `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
)

const (
    LLMHUB_URL = "${baseUrl}/api/v1"
    API_KEY    = "${client.api_key}"
)`

  const contentExample = `type ContentRequest struct {
    Prompt      string   \`json:"prompt"\`
    Provider    string   \`json:"provider"\`
    Model       string   \`json:"model"\`
    MaxTokens   int      \`json:"max_tokens"\`
    Temperature float64  \`json:"temperature"\`
}

type ContentResponse struct {
    Content    string  \`json:"content"\`
    TokensUsed int     \`json:"tokens_used"\`
    CostUSD    float64 \`json:"cost_usd"\`
}

func GenerateContent(prompt string) (string, error) {
    reqBody := ContentRequest{
        Prompt:      prompt,
        Provider:    "claude",
        Model:       "claude-3-5-sonnet-20241022",
        MaxTokens:   1000,
        Temperature: 0.7,
    }

    jsonData, err := json.Marshal(reqBody)
    if err != nil {
        return "", err
    }

    req, err := http.NewRequest("POST", LLMHUB_URL+"/llm/generate-content",
        bytes.NewBuffer(jsonData))
    if err != nil {
        return "", err
    }

    req.Header.Set("X-API-Key", API_KEY)
    req.Header.Set("Content-Type", "application/json")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()

    body, err := ioutil.ReadAll(resp.Body)
    if err != nil {
        return "", err
    }

    var result ContentResponse
    err = json.Unmarshal(body, &result)
    if err != nil {
        return "", err
    }

    return result.Content, nil
}

func main() {
    content, err := GenerateContent("Explain quantum computing")
    if err != nil {
        fmt.Println("Error:", err)
        return
    }
    fmt.Println(content)
}`

  return (
    <div class="space-y-6">
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Setup</h3>
        <CodeBlock code={setupCode} language="go" copyToClipboard={copyToClipboard} label="Go setup" />
      </div>
      <div>
        <h3 class="font-semibold text-gray-900 mb-2">Generate Content</h3>
        <CodeBlock code={contentExample} language="go" copyToClipboard={copyToClipboard} label="Go content example" />
      </div>
    </div>
  )
}

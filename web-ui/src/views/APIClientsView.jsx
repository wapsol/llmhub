import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'

export default function APIClientsView() {
  const [loading, setLoading] = useState(true)
  const [clients, setClients] = useState([])
  const [showKeys, setShowKeys] = useState({})
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newClient, setNewClient] = useState({
    client_name: '',
    organization: '',
    contact_email: '',
    rate_limit: 100,
    monthly_budget_usd: null
  })

  const maskApiKey = (key) => {
    if (!key) return ''
    const prefix = key.substring(0, 12)
    return `${prefix}${'*'.repeat(20)}`
  }

  const toggleKeyVisibility = (clientId) => {
    setShowKeys(prev => ({ ...prev, [clientId]: !prev[clientId] }))
  }

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      alert('API key copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString()
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

  useEffect(() => {
    loadClients()
  }, [])

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">API Clients</h1>
        <button onClick={() => setShowCreateModal(true)} class="btn-primary">
          <svg class="inline-block w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
          </svg>
          Create Client
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Clients List */}
      {!loading && (
        <div class="space-y-4">
          {clients.map((client) => (
            <div key={client.client_id} class="card">
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <div class="flex items-center space-x-3">
                    <h3 class="text-lg font-semibold text-gray-900">{client.client_name}</h3>
                    <span class={`badge ${client.is_active ? 'badge-success' : 'badge-danger'}`}>
                      {client.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  {client.organization && <p class="text-sm text-gray-600 mt-1">{client.organization}</p>}
                  {client.contact_email && <p class="text-sm text-gray-500 mt-1">{client.contact_email}</p>}

                  {/* API Key */}
                  <div class="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div class="flex items-center justify-between">
                      <div class="flex-1">
                        <p class="text-xs font-medium text-gray-700 mb-1">API Key</p>
                        <code class="text-sm font-mono text-gray-900 break-all">
                          {showKeys[client.client_id] ? client.api_key : maskApiKey(client.api_key)}
                        </code>
                      </div>
                      <div class="flex items-center space-x-2 ml-4">
                        <button
                          onClick={() => toggleKeyVisibility(client.client_id)}
                          class="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                          title={showKeys[client.client_id] ? 'Hide' : 'Show'}
                        >
                          {!showKeys[client.client_id] ? (
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                            </svg>
                          ) : (
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"></path>
                            </svg>
                          )}
                        </button>
                        <button
                          onClick={() => copyToClipboard(client.api_key)}
                          class="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                          title="Copy"
                        >
                          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Stats */}
                  <div class="grid grid-cols-3 gap-4 mt-4">
                    <div>
                      <p class="text-xs text-gray-600">Rate Limit</p>
                      <p class="text-sm font-medium text-gray-900 mt-1">{client.rate_limit || 100}/min</p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-600">Monthly Budget</p>
                      <p class="text-sm font-medium text-gray-900 mt-1">
                        {client.monthly_budget_usd ? `$${client.monthly_budget_usd}` : 'Unlimited'}
                      </p>
                    </div>
                    <div>
                      <p class="text-xs text-gray-600">Created</p>
                      <p class="text-sm font-medium text-gray-900 mt-1">{formatDate(client.created_at)}</p>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div class="ml-6 flex flex-col space-y-2">
                  <button onClick={() => regenerateKey(client)} class="btn-secondary text-sm">
                    Regenerate Key
                  </button>
                  <button onClick={() => deleteClient(client)} class="btn-danger text-sm">
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
                <label class="label">Monthly Budget (USD)</label>
                <input
                  value={newClient.monthly_budget_usd || ''}
                  onInput={(e) => setNewClient({ ...newClient, monthly_budget_usd: parseFloat(e.target.value) || null })}
                  type="number"
                  step="0.01"
                  class="input"
                  placeholder="500.00"
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
    </div>
  )
}

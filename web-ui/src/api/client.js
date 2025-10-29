import axios from 'axios'

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any default headers or auth here if needed
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error.response?.data || error)
  }
)

// API methods
export const api = {
  // Health check
  health: () => axios.get('/health'),

  // Admin endpoints
  admin: {
    // Get dashboard stats
    getStats: () => apiClient.get('/admin/stats'),

    // Providers
    getProviders: () => apiClient.get('/admin/providers'),
    getProviderModels: (providerId) => apiClient.get(`/admin/providers/${providerId}/models`),
    updateProviderApiKey: (providerKey, apiKey) => apiClient.put(`/admin/providers/${providerKey}/api-key`, { api_key: apiKey }),
    deleteProviderApiKey: (providerKey) => apiClient.delete(`/admin/providers/${providerKey}/api-key`),
    testProviderApiKey: (providerKey, apiKey = null) => {
      const body = apiKey ? { api_key: apiKey } : {}
      return apiClient.post(`/admin/providers/${providerKey}/test-key`, body)
    },

    // Models
    getAllModels: (providerKey = null) => {
      const params = providerKey ? { provider_key: providerKey } : {}
      return apiClient.get('/admin/models', { params })
    },
    updateModel: (modelId, data) => apiClient.patch(`/admin/models/${modelId}`, data),
    toggleModel: (modelId) => apiClient.post(`/admin/models/${modelId}/toggle`),

    // API Clients
    getClients: () => apiClient.get('/admin/clients'),
    createClient: (data) => apiClient.post('/admin/clients', data),
    updateClient: (clientId, data) => apiClient.patch(`/admin/clients/${clientId}`, data),
    deleteClient: (clientId) => apiClient.delete(`/admin/clients/${clientId}`),
    regenerateKey: (clientId) => apiClient.post(`/admin/clients/${clientId}/regenerate-key`),

    // Templates
    getTemplates: () => apiClient.get('/llm/prompts'),
    getTemplate: (templateId) => apiClient.get(`/llm/prompts/${templateId}`),

    // Billing
    getOrganizations: () => apiClient.get('/admin/billing/organizations'),
    getBillingStats: (params) => apiClient.get('/admin/billing/stats', { params }),
    getDailyCosts: (params) => apiClient.get('/admin/billing/daily', { params }),
    getClientCosts: (params) => apiClient.get('/admin/billing/by-client', { params }),
    getClientsByOrganization: (organization) => apiClient.get('/admin/clients', { params: { organization } })
  }
}

export default apiClient

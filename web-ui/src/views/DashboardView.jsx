import { useState, useEffect } from 'preact/hooks'
import { Link } from 'preact-router/match'
import { route } from 'preact-router'
import { api } from '@/api/client'
import SystemMessage, { useSystemMessage } from '@/components/system_message'

export default function DashboardView() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    totalClients: 0,
    totalTemplates: 0,
    totalCalls: 0,
    totalCost: 0
  })
  const [providers, setProviders] = useState([])
  const { message, type, showMessage } = useSystemMessage()

  const formatNumber = (num) => {
    return new Intl.NumberFormat('de-DE').format(num)
  }

  const formatCurrency = (num) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(num)
  }

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [statsData, providersData] = await Promise.all([
          api.admin.getStats(),
          api.admin.getProviders()
        ])
        setStats(statsData)
        setProviders(providersData)
        setLoading(false)
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
        setLoading(false)
      }
    }
    loadDashboardData()
  }, [])

  const handleProviderClick = (provider) => {
    // Navigate to models page with provider filter
    route(`/models?provider=${provider.provider_key}`)
  }

  if (loading) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Dashboard</h1>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Dashboard</h1>
        <div class="flex-1 max-w-2xl ml-4">
          <SystemMessage type={type} message={message} />
        </div>
      </div>

      {/* Stats Grid */}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-600">API Clients</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{stats.totalClients}</p>
            </div>
            <div class="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <svg class="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
              </svg>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-600">Prompt Templates</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{stats.totalTemplates}</p>
            </div>
            <div class="h-12 w-12 bg-green-100 rounded-lg flex items-center justify-center">
              <svg class="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
              </svg>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-600">Usage (Last 30 days)</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{formatNumber(stats.totalCalls)}</p>
              <p class="text-lg font-semibold text-primary-600 mt-1">{formatCurrency(stats.totalCost)}</p>
            </div>
            <div class="h-12 w-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <svg class="h-6 w-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Providers Overview */}
      <div class="card mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">LLM Providers</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          {providers.map((provider) => (
            <div
              key={provider.provider_id}
              class="p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-primary-500 hover:shadow-md transition-all"
              onClick={() => handleProviderClick(provider)}
            >
              <div class="flex items-center justify-between mb-2">
                <h3 class="font-medium text-gray-900">{provider.display_name}</h3>
                <span class={`badge ${provider.api_key_configured ? 'badge-success' : 'badge-warning'}`}>
                  {provider.api_key_configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <p class="text-sm text-gray-600 mb-2">{provider.model_count} models available</p>
              <p class="text-xs text-gray-500">{provider.description}</p>
              <p class="text-xs text-primary-600 mt-2 font-medium">Click to view models →</p>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div class="card">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/clients" class="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 transition-colors">
            <h3 class="font-medium text-gray-900 mb-1">Create API Client</h3>
            <p class="text-sm text-gray-600">Add a new application to use LLMHub</p>
          </Link>
          <Link href="/models" class="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 transition-colors">
            <h3 class="font-medium text-gray-900 mb-1">Manage Models</h3>
            <p class="text-sm text-gray-600">Configure model pricing and availability</p>
          </Link>
          <Link href="/billing" class="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 transition-colors">
            <h3 class="font-medium text-gray-900 mb-1">View Billing</h3>
            <p class="text-sm text-gray-600">Analyze usage costs and trends</p>
          </Link>
        </div>
      </div>
    </div>
  )
}

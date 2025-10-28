import { useState, useEffect } from 'preact/hooks'
import { Link } from 'preact-router/match'
import { api } from '@/api/client'

export default function DashboardView() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    totalClients: 0,
    totalTemplates: 0,
    totalCalls: 0,
    totalCost: 0
  })

  const [providers] = useState([
    {
      name: 'Anthropic Claude',
      models: 3,
      configured: false,
      description: 'Advanced AI assistant with long context'
    },
    {
      name: 'OpenAI',
      models: 4,
      configured: false,
      description: 'GPT-4 and DALL-E image generation'
    },
    {
      name: 'Groq',
      models: 2,
      configured: false,
      description: 'Ultra-fast inference with Mixtral'
    }
  ])

  const formatNumber = (num) => {
    return new Intl.NumberFormat().format(num)
  }

  const formatCurrency = (num) => {
    return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num)
  }

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await api.admin.getStats()
        setStats(data)
        setLoading(false)
      } catch (error) {
        console.error('Failed to load dashboard stats:', error)
        setLoading(false)
      }
    }
    loadStats()
  }, [])

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
      <h1 class="text-3xl font-bold text-gray-900 mb-8">Dashboard</h1>

      {/* Stats Grid */}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-600">Total API Clients</p>
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
              <p class="text-sm font-medium text-gray-600">Total LLM Calls</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{formatNumber(stats.totalCalls)}</p>
              <p class="text-xs text-gray-500 mt-1">Last 30 days</p>
            </div>
            <div class="h-12 w-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <svg class="h-6 w-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
              </svg>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-600">Total Cost (USD)</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">${formatCurrency(stats.totalCost)}</p>
              <p class="text-xs text-gray-500 mt-1">Last 30 days</p>
            </div>
            <div class="h-12 w-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <svg class="h-6 w-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
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
            <div key={provider.name} class="p-4 border border-gray-200 rounded-lg">
              <div class="flex items-center justify-between mb-2">
                <h3 class="font-medium text-gray-900">{provider.name}</h3>
                <span class={`badge ${provider.configured ? 'badge-success' : 'badge-warning'}`}>
                  {provider.configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <p class="text-sm text-gray-600 mb-2">{provider.models} models available</p>
              <p class="text-xs text-gray-500">{provider.description}</p>
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
          <Link href="/providers" class="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 transition-colors">
            <h3 class="font-medium text-gray-900 mb-1">View Providers</h3>
            <p class="text-sm text-gray-600">Check provider status and models</p>
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

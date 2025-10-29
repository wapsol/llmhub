import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'

export default function BillingView() {
  const [loading, setLoading] = useState(true)
  const [selectedRange, setSelectedRange] = useState(30)
  const [organizations, setOrganizations] = useState([])
  const [selectedOrganization, setSelectedOrganization] = useState('')
  const [clientNames, setClientNames] = useState([])
  const [selectedClientName, setSelectedClientName] = useState('')
  const [stats, setStats] = useState({
    totalCost: 0,
    totalCalls: 0,
    avgCostPerCall: 0
  })
  const [providerCosts, setProviderCosts] = useState([])
  const [clientCosts, setClientCosts] = useState([])
  const [dailyCosts, setDailyCosts] = useState([])

  const formatNumber = (num) => {
    return new Intl.NumberFormat('de-DE').format(num || 0)
  }

  const formatCurrency = (num) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(num || 0)
  }

  const loadOrganizations = async () => {
    try {
      const orgs = await api.admin.getOrganizations()
      setOrganizations(orgs)
    } catch (error) {
      console.error('Failed to load organizations:', error)
    }
  }

  const loadClientsForOrganization = async (organization) => {
    if (!organization) {
      setClientNames([])
      return
    }
    try {
      const clients = await api.admin.getClients()
      const filtered = clients
        .filter(c => c.organization === organization)
        .map(c => c.client_name)
      setClientNames(filtered)
    } catch (error) {
      console.error('Failed to load clients:', error)
    }
  }

  const loadBillingData = async () => {
    setLoading(true)
    try {
      // Build params with filters
      const params = { days: selectedRange }
      if (selectedOrganization) {
        params.organization = selectedOrganization
      }
      if (selectedClientName) {
        params.client_name = selectedClientName
      }

      // Load billing stats
      const statsData = await api.admin.getBillingStats(params)
      setStats(statsData)

      // Load provider costs
      const providersData = await api.admin.getDailyCosts(params)

      // Aggregate by provider
      const providerMap = {}
      providersData.forEach(day => {
        if (!providerMap[day.provider]) {
          providerMap[day.provider] = { cost: 0, calls: 0 }
        }
        providerMap[day.provider].cost += parseFloat(day.total_cost || 0)
        providerMap[day.provider].calls += parseInt(day.total_calls || 0)
      })

      const totalCost = Object.values(providerMap).reduce((sum, p) => sum + p.cost, 0)

      const providers = Object.entries(providerMap).map(([name, data]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        cost: data.cost,
        calls: data.calls,
        percentage: totalCost > 0 ? (data.cost / totalCost) * 100 : 0,
        color: name === 'claude' ? 'bg-purple-500' : name === 'openai' ? 'bg-green-500' : 'bg-orange-500'
      })).sort((a, b) => b.cost - a.cost)

      setProviderCosts(providers)

      // Load client costs
      const clientsData = await api.admin.getClientCosts(params)
      const clients = clientsData.map(client => ({
        ...client,
        budget_percent: client.monthly_budget ? (client.total_cost / client.monthly_budget) * 100 : 0
      }))
      setClientCosts(clients)

      // Load daily costs
      const maxCost = Math.max(...providersData.map(d => parseFloat(d.total_cost || 0)))
      const daily = providersData.slice(-selectedRange).map(day => ({
        date: new Date(day.day).toLocaleDateString('de-DE', { day: '2-digit', month: 'short' }),
        cost: parseFloat(day.total_cost || 0),
        percentage: maxCost > 0 ? (parseFloat(day.total_cost || 0) / maxCost) * 100 : 0
      }))
      setDailyCosts(daily)

    } catch (error) {
      console.error('Failed to load billing data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOrganizations()
  }, [])

  useEffect(() => {
    loadBillingData()
  }, [selectedRange, selectedOrganization, selectedClientName])

  useEffect(() => {
    if (selectedOrganization) {
      loadClientsForOrganization(selectedOrganization)
      setSelectedClientName('') // Reset client selection when organization changes
    } else {
      setClientNames([])
      setSelectedClientName('')
    }
  }, [selectedOrganization])

  return (
    <div>
      <h1 class="text-3xl font-bold text-gray-900 mb-8">Billing & Usage</h1>

      {/* Filters */}
      <div class="card mb-6">
        <div class="flex flex-wrap items-center gap-4">
          {/* Time Range */}
          <div class="flex items-center space-x-2">
            <label class="text-sm font-medium text-gray-700">Time Range:</label>
            <select
              value={selectedRange}
              onChange={(e) => setSelectedRange(parseInt(e.target.value))}
              class="input w-48"
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </div>

          {/* Organization Filter */}
          <div class="flex items-center space-x-2">
            <label class="text-sm font-medium text-gray-700">Organization:</label>
            <input
              type="text"
              list="organizations-list"
              value={selectedOrganization}
              onChange={(e) => setSelectedOrganization(e.target.value)}
              placeholder="All organizations"
              class="input w-64"
            />
            <datalist id="organizations-list">
              {organizations.map(org => (
                <option key={org} value={org}>{org}</option>
              ))}
            </datalist>
            {selectedOrganization && (
              <button
                onClick={() => setSelectedOrganization('')}
                class="text-sm text-gray-500 hover:text-gray-700"
                title="Clear filter"
              >
                ✕
              </button>
            )}
          </div>

          {/* Client Filter (only shown when organization is selected) */}
          {selectedOrganization && clientNames.length > 0 && (
            <div class="flex items-center space-x-2">
              <label class="text-sm font-medium text-gray-700">Client:</label>
              <select
                value={selectedClientName}
                onChange={(e) => setSelectedClientName(e.target.value)}
                class="input w-64"
              >
                <option value="">All Clients</option>
                {clientNames.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Summary Stats */}
      {!loading && (
        <div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="card">
              <p class="text-sm font-medium text-gray-600">Total Cost</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{formatCurrency(stats.totalCost)}</p>
              <p class="text-xs text-gray-500 mt-1">{selectedRange} days</p>
            </div>

            <div class="card">
              <p class="text-sm font-medium text-gray-600">Total Calls</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{formatNumber(stats.totalCalls)}</p>
              <p class="text-xs text-gray-500 mt-1">{selectedRange} days</p>
            </div>

            <div class="card">
              <p class="text-sm font-medium text-gray-600">Avg Cost Per Call</p>
              <p class="text-3xl font-bold text-gray-900 mt-2">{formatCurrency(stats.avgCostPerCall)}</p>
              <p class="text-xs text-gray-500 mt-1">{selectedRange} days</p>
            </div>
          </div>

          {/* Cost by Provider */}
          <div class="card mb-8">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Cost by Provider</h2>
            <div class="space-y-4">
              {providerCosts.map((provider) => (
                <div key={provider.name} class="flex items-center">
                  <div class="flex-1">
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-sm font-medium text-gray-700">{provider.name}</span>
                      <span class="text-sm font-medium text-gray-900">{formatCurrency(provider.cost)}</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                      <div
                        class={`h-2 rounded-full ${provider.color}`}
                        style={{ width: `${provider.percentage}%` }}
                      ></div>
                    </div>
                    <div class="flex items-center justify-between mt-1">
                      <span class="text-xs text-gray-500">{formatNumber(provider.calls)} calls</span>
                      <span class="text-xs text-gray-500">{provider.percentage.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              ))}

              {providerCosts.length === 0 && (
                <div class="text-center py-8 text-gray-500">
                  No usage data for selected time range
                </div>
              )}
            </div>
          </div>

          {/* Cost by Client */}
          <div class="card mb-8">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Cost by API Client</h2>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Organization</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Calls</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tokens</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cost</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Budget</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">% Used</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                  {clientCosts.map((client) => (
                    <tr key={client.client_name}>
                      <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{client.organization || '-'}</td>
                      <td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{client.client_name}</td>
                      <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatNumber(client.total_calls)}</td>
                      <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatNumber(client.total_tokens)}</td>
                      <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900 font-medium">{formatCurrency(client.total_cost)}</td>
                      <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {client.monthly_budget ? formatCurrency(client.monthly_budget) : 'Unlimited'}
                      </td>
                      <td class="px-4 py-3 whitespace-nowrap">
                        {client.monthly_budget ? (
                          <span
                            class={`badge ${
                              client.budget_percent < 50
                                ? 'badge-success'
                                : client.budget_percent >= 50 && client.budget_percent < 80
                                ? 'badge-warning'
                                : 'badge-danger'
                            }`}
                          >
                            {client.budget_percent.toFixed(1)}%
                          </span>
                        ) : (
                          <span class="text-sm text-gray-500">N/A</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {clientCosts.length === 0 && (
                <div class="text-center py-8 text-gray-500">
                  No client usage data for selected time range
                </div>
              )}
            </div>
          </div>

          {/* Daily Costs Chart (Simple Text-based) */}
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Daily Costs</h2>
            <div class="space-y-2">
              {dailyCosts.map((day) => (
                <div key={day.date} class="flex items-center">
                  <div class="w-24 text-sm text-gray-600">{day.date}</div>
                  <div class="flex-1 flex items-center">
                    <div
                      class="bg-primary-500 h-6 rounded"
                      style={{ width: `${day.percentage}%` }}
                    ></div>
                    <span class="ml-2 text-sm font-medium text-gray-900">{formatCurrency(day.cost)}</span>
                  </div>
                </div>
              ))}

              {dailyCosts.length === 0 && (
                <div class="text-center py-8 text-gray-500">
                  No daily cost data for selected time range
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

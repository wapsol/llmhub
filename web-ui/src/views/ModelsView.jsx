import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'

export default function ModelsView({ provider: urlProvider }) {
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState([])
  const [selectedProvider, setSelectedProvider] = useState('all')
  const [editingModel, setEditingModel] = useState(null)
  const [editValues, setEditValues] = useState({})

  // Initialize selected provider from URL parameter
  useEffect(() => {
    if (urlProvider) {
      setSelectedProvider(urlProvider)
    }
  }, [urlProvider])

  useEffect(() => {
    loadData()
  }, [selectedProvider])

  const loadData = async () => {
    setLoading(true)
    try {
      const [providersData, modelsData] = await Promise.all([
        api.admin.getProvidersRegistry(),
        api.admin.getAllModels(selectedProvider === 'all' ? null : selectedProvider)
      ])
      setProviders(providersData)
      setModels(modelsData)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleProviderChange = (e) => {
    setSelectedProvider(e.target.value)
    setEditingModel(null)
  }

  const startEditing = (model) => {
    setEditingModel(model.model_id)
    setEditValues({
      cost_per_million_input: model.cost_per_million_input,
      cost_per_million_output: model.cost_per_million_output,
      price_per_million_input: model.price_per_million_input,
      price_per_million_output: model.price_per_million_output
    })
  }

  const cancelEditing = () => {
    setEditingModel(null)
    setEditValues({})
  }

  const saveModel = async (modelId) => {
    try {
      await api.admin.updateModel(modelId, editValues)
      setEditingModel(null)
      setEditValues({})
      // Reload data to show updated values
      loadData()
    } catch (error) {
      console.error('Failed to update model:', error)
      alert('Failed to update model. Please try again.')
    }
  }

  const toggleModelStatus = async (modelId) => {
    try {
      await api.admin.toggleModel(modelId)
      // Reload data to show updated status
      loadData()
    } catch (error) {
      console.error('Failed to toggle model:', error)
      alert('Failed to toggle model. Please try again.')
    }
  }

  const formatCost = (cost) => {
    return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 }).format(cost)
  }

  const updateEditValue = (field, value) => {
    setEditValues(prev => ({ ...prev, [field]: parseFloat(value) || 0 }))
  }

  if (loading) {
    return (
      <div>
        <div class="flex justify-between items-center mb-8">
          <h1 class="text-3xl font-bold text-gray-900">Models</h1>
        </div>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header with Provider Filter */}
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Models</h1>
        <div class="flex items-center space-x-3">
          <label class="text-sm font-medium text-gray-700">Provider:</label>
          <select
            value={selectedProvider}
            onChange={handleProviderChange}
            class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">All Providers</option>
            {providers.map((provider) => (
              <option key={provider.provider_key} value={provider.provider_key}>
                {provider.display_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Models Table */}
      <div class="card overflow-hidden">
        {models.length === 0 ? (
          <div class="p-8 text-center text-gray-500">
            No models found for the selected provider.
          </div>
        ) : (
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Model
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Context
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cost (Input)
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cost (Output)
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Price (Input)
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Price (Output)
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                {models.map((model) => (
                  <tr key={model.model_id} class="hover:bg-gray-50">
                    <td class="px-6 py-4">
                      <div>
                        <div class="text-sm font-medium text-gray-900">{model.display_name}</div>
                        <div class="text-xs text-gray-500">{model.description}</div>
                      </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {model.context_window}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      {editingModel === model.model_id ? (
                        <input
                          type="number"
                          step="0.000001"
                          value={editValues.cost_per_million_input}
                          onChange={(e) => updateEditValue('cost_per_million_input', e.target.value)}
                          class="w-24 px-2 py-1 border border-gray-300 rounded text-xs"
                        />
                      ) : (
                        <span class="text-gray-700">${formatCost(model.cost_per_million_input)}</span>
                      )}
                      <div class="text-xs text-gray-400">/1M tokens</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      {editingModel === model.model_id ? (
                        <input
                          type="number"
                          step="0.000001"
                          value={editValues.cost_per_million_output}
                          onChange={(e) => updateEditValue('cost_per_million_output', e.target.value)}
                          class="w-24 px-2 py-1 border border-gray-300 rounded text-xs"
                        />
                      ) : (
                        <span class="text-gray-700">${formatCost(model.cost_per_million_output)}</span>
                      )}
                      <div class="text-xs text-gray-400">/1M tokens</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      {editingModel === model.model_id ? (
                        <input
                          type="number"
                          step="0.000001"
                          value={editValues.price_per_million_input}
                          onChange={(e) => updateEditValue('price_per_million_input', e.target.value)}
                          class="w-24 px-2 py-1 border border-blue-300 rounded text-xs"
                        />
                      ) : (
                        <span class="text-blue-600 font-medium">${formatCost(model.price_per_million_input)}</span>
                      )}
                      <div class="text-xs text-gray-400">/1M tokens</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      {editingModel === model.model_id ? (
                        <input
                          type="number"
                          step="0.000001"
                          value={editValues.price_per_million_output}
                          onChange={(e) => updateEditValue('price_per_million_output', e.target.value)}
                          class="w-24 px-2 py-1 border border-blue-300 rounded text-xs"
                        />
                      ) : (
                        <span class="text-blue-600 font-medium">${formatCost(model.price_per_million_output)}</span>
                      )}
                      <div class="text-xs text-gray-400">/1M tokens</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => toggleModelStatus(model.model_id)}
                        class={`px-3 py-1 rounded-full text-xs font-medium ${
                          model.is_enabled
                            ? 'bg-green-100 text-green-800 hover:bg-green-200'
                            : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                        } transition-colors`}
                      >
                        {model.is_enabled ? 'Enabled' : 'Disabled'}
                      </button>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      {editingModel === model.model_id ? (
                        <div class="flex justify-end space-x-2">
                          <button
                            onClick={() => saveModel(model.model_id)}
                            class="text-green-600 hover:text-green-900"
                          >
                            Save
                          </button>
                          <button
                            onClick={cancelEditing}
                            class="text-gray-600 hover:text-gray-900"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => startEditing(model)}
                          class="text-primary-600 hover:text-primary-900"
                        >
                          Edit Pricing
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Info Section */}
      <div class="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 class="text-sm font-medium text-blue-900 mb-2">Pricing Configuration</h3>
        <ul class="text-sm text-blue-800 space-y-1">
          <li><strong>Cost:</strong> The amount charged by the provider per 1 million tokens</li>
          <li><strong>Price:</strong> The amount you charge to your API clients per 1 million tokens</li>
          <li><strong>Margin:</strong> The difference between Price and Cost is your profit margin</li>
          <li><strong>Status:</strong> Only enabled models can be used for new API requests</li>
        </ul>
      </div>
    </div>
  )
}

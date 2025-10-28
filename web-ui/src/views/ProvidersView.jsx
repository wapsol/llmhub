import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'

export default function ProvidersView() {
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState({
    claude: {
      configured: false,
      models: [
        {
          id: 'claude-3-5-sonnet-20241022',
          name: 'Claude 3.5 Sonnet',
          description: 'Most intelligent model, best for complex tasks',
          inputCost: 0.003,
          outputCost: 0.015,
          contextWindow: '200K',
          enabled: true
        },
        {
          id: 'claude-3-opus-20240229',
          name: 'Claude 3 Opus',
          description: 'Powerful model for highly complex tasks',
          inputCost: 0.015,
          outputCost: 0.075,
          contextWindow: '200K',
          enabled: false
        },
        {
          id: 'claude-3-haiku-20240307',
          name: 'Claude 3 Haiku',
          description: 'Fast and cost-effective for simple tasks',
          inputCost: 0.00025,
          outputCost: 0.00125,
          contextWindow: '200K',
          enabled: true
        }
      ]
    },
    openai: {
      configured: false,
      models: [
        {
          id: 'gpt-4-turbo-preview',
          name: 'GPT-4 Turbo',
          description: 'Most capable model with improved efficiency',
          inputCost: 0.01,
          outputCost: 0.03,
          contextWindow: '128K',
          enabled: true
        },
        {
          id: 'gpt-4',
          name: 'GPT-4',
          description: 'Original GPT-4 model',
          inputCost: 0.03,
          outputCost: 0.06,
          contextWindow: '8K',
          enabled: false
        },
        {
          id: 'gpt-3.5-turbo',
          name: 'GPT-3.5 Turbo',
          description: 'Fast and cost-effective',
          inputCost: 0.0015,
          outputCost: 0.002,
          contextWindow: '16K',
          enabled: true
        }
      ]
    },
    groq: {
      configured: false,
      models: [
        {
          id: 'mixtral-8x7b-32768',
          name: 'Mixtral 8x7B',
          description: 'High quality open-source model',
          inputCost: 0.00027,
          outputCost: 0.00027,
          contextWindow: '32K',
          enabled: true
        },
        {
          id: 'llama2-70b-4096',
          name: 'LLaMA 2 70B',
          description: 'Large open-source model',
          inputCost: 0.00007,
          outputCost: 0.00007,
          contextWindow: '4K',
          enabled: false
        }
      ]
    }
  })

  const toggleModel = (model) => {
    console.log(`Model ${model.id} enabled:`, model.enabled)
    // In a real implementation, this would save to backend
  }

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const data = await api.admin.getProviders()
        // Update configured status based on API response
        setProviders(prev => ({
          claude: { ...prev.claude, configured: data.claude_configured || false },
          openai: { ...prev.openai, configured: data.openai_configured || false },
          groq: { ...prev.groq, configured: data.groq_configured || false }
        }))
      } catch (error) {
        console.error('Failed to load providers:', error)
      } finally {
        setLoading(false)
      }
    }
    loadProviders()
  }, [])

  if (loading) {
    return (
      <div>
        <div class="flex justify-between items-center mb-8">
          <h1 class="text-3xl font-bold text-gray-900">Providers & Models</h1>
        </div>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Providers & Models</h1>
      </div>

      {/* Providers List */}
      <div class="space-y-6">
        {/* Anthropic Claude */}
        <div class="card">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-xl font-semibold text-gray-900">Anthropic Claude</h2>
              <p class="text-sm text-gray-600 mt-1">Advanced AI assistant with 200K context window</p>
            </div>
            <span class={`badge ${providers.claude.configured ? 'badge-success' : 'badge-warning'}`}>
              {providers.claude.configured ? 'Configured' : 'API Key Not Set'}
            </span>
          </div>

          <div class="space-y-3">
            {providers.claude.models.map((model) => (
              <div key={model.id} class="p-4 border border-gray-200 rounded-lg">
                <div class="flex items-center justify-between">
                  <div class="flex-1">
                    <h3 class="font-medium text-gray-900">{model.name}</h3>
                    <p class="text-sm text-gray-600 mt-1">{model.description}</p>
                    <div class="flex items-center space-x-4 mt-2">
                      <span class="text-xs text-gray-500">Input: ${model.inputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Output: ${model.outputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Context: {model.contextWindow}</span>
                    </div>
                  </div>
                  <div class="ml-4">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={model.enabled}
                        class="sr-only peer"
                        onChange={(e) => {
                          model.enabled = e.target.checked
                          toggleModel(model)
                        }}
                      />
                      <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* OpenAI */}
        <div class="card">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-xl font-semibold text-gray-900">OpenAI</h2>
              <p class="text-sm text-gray-600 mt-1">GPT-4 and image generation with DALL-E</p>
            </div>
            <span class={`badge ${providers.openai.configured ? 'badge-success' : 'badge-warning'}`}>
              {providers.openai.configured ? 'Configured' : 'API Key Not Set'}
            </span>
          </div>

          <div class="space-y-3">
            {providers.openai.models.map((model) => (
              <div key={model.id} class="p-4 border border-gray-200 rounded-lg">
                <div class="flex items-center justify-between">
                  <div class="flex-1">
                    <h3 class="font-medium text-gray-900">{model.name}</h3>
                    <p class="text-sm text-gray-600 mt-1">{model.description}</p>
                    <div class="flex items-center space-x-4 mt-2">
                      <span class="text-xs text-gray-500">Input: ${model.inputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Output: ${model.outputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Context: {model.contextWindow}</span>
                    </div>
                  </div>
                  <div class="ml-4">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={model.enabled}
                        class="sr-only peer"
                        onChange={(e) => {
                          model.enabled = e.target.checked
                          toggleModel(model)
                        }}
                      />
                      <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Groq */}
        <div class="card">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-xl font-semibold text-gray-900">Groq</h2>
              <p class="text-sm text-gray-600 mt-1">Ultra-fast inference with open-source models</p>
            </div>
            <span class={`badge ${providers.groq.configured ? 'badge-success' : 'badge-warning'}`}>
              {providers.groq.configured ? 'Configured' : 'API Key Not Set'}
            </span>
          </div>

          <div class="space-y-3">
            {providers.groq.models.map((model) => (
              <div key={model.id} class="p-4 border border-gray-200 rounded-lg">
                <div class="flex items-center justify-between">
                  <div class="flex-1">
                    <h3 class="font-medium text-gray-900">{model.name}</h3>
                    <p class="text-sm text-gray-600 mt-1">{model.description}</p>
                    <div class="flex items-center space-x-4 mt-2">
                      <span class="text-xs text-gray-500">Input: ${model.inputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Output: ${model.outputCost}/1K tokens</span>
                      <span class="text-xs text-gray-500">Context: {model.contextWindow}</span>
                    </div>
                  </div>
                  <div class="ml-4">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={model.enabled}
                        class="sr-only peer"
                        onChange={(e) => {
                          model.enabled = e.target.checked
                          toggleModel(model)
                        }}
                      />
                      <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * TestStatusDisplay Component
 * Shows real-time step-by-step status of API key testing
 */

export default function TestStatusDisplay({ steps, isLoading }) {
  const getStepIcon = (status) => {
    switch (status) {
      case 'running':
        return (
          <div class="animate-spin rounded-full h-5 w-5 border-2 border-primary-600 border-t-transparent"></div>
        )
      case 'success':
        return (
          <svg class="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
          </svg>
        )
      case 'failed':
        return (
          <svg class="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
          </svg>
        )
      default:
        return (
          <div class="h-5 w-5 rounded-full border-2 border-gray-300"></div>
        )
    }
  }

  const getStepColor = (status) => {
    switch (status) {
      case 'running':
        return 'bg-blue-50 border-blue-200'
      case 'success':
        return 'bg-green-50 border-green-200'
      case 'failed':
        return 'bg-red-50 border-red-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  const getStepLabel = (stepName) => {
    const labels = {
      validate_provider: 'Validate Provider',
      get_api_key: 'Retrieve API Key',
      init_client: 'Initialize Client',
      authenticate: 'Authenticate',
      fetch_models: 'Fetch Models & Pricing'
    }
    return labels[stepName] || stepName
  }

  if (!steps || steps.length === 0) {
    return null
  }

  return (
    <div class="mt-4 space-y-2">
      <h4 class="text-sm font-medium text-gray-700">Connection Status</h4>
      <div class="space-y-2">
        {steps.map((step, index) => (
          <div
            key={`${step.step}-${index}`}
            class={`p-3 rounded-lg border ${getStepColor(step.status)}`}
          >
            <div class="flex items-start">
              <div class="flex-shrink-0 mt-0.5">
                {getStepIcon(step.status)}
              </div>
              <div class="ml-3 flex-1">
                <div class="flex items-center justify-between">
                  <p class="text-sm font-medium text-gray-900">
                    {getStepLabel(step.step)}
                  </p>
                  {step.status === 'running' && (
                    <span class="text-xs text-blue-600 font-medium">In Progress...</span>
                  )}
                </div>
                {step.message && (
                  <p class="text-xs text-gray-600 mt-1">{step.message}</p>
                )}
                {step.error && (
                  <p class="text-xs text-red-700 mt-1 font-medium">{step.error}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

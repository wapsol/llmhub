import Modal from './Modal'

/**
 * ProtocolModal Component
 * Displays test protocol in plain text format with color-coded messages
 */
export default function ProtocolModal({ isOpen, onClose, providerName, testResults }) {
  if (!testResults || !testResults.steps) {
    return null
  }

  const getStepStatusText = (status) => {
    switch (status) {
      case 'success':
        return '✓'
      case 'failed':
        return '✗'
      case 'running':
        return '→'
      default:
        return '○'
    }
  }

  const getStepColor = (status) => {
    switch (status) {
      case 'success':
        return 'text-green-600'
      case 'failed':
        return 'text-red-600'
      case 'running':
        return 'text-blue-600'
      default:
        return 'text-gray-500'
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

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`${providerName} - Connection Protocol`} size="lg">
      <div class="space-y-3">
        {/* Overall Status */}
        <div class={`p-3 rounded-lg font-mono text-sm ${testResults.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {testResults.success ? '✓ CONNECTION SUCCESSFUL' : '✗ CONNECTION FAILED'}
          {testResults.message && <div class="mt-1">{testResults.message}</div>}
          {testResults.error && <div class="mt-1 font-semibold">{testResults.error}</div>}
        </div>

        {/* Step-by-Step Protocol */}
        <div class="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-2 max-h-96 overflow-y-auto">
          {testResults.steps.map((step, index) => (
            <div key={`${step.step}-${index}`} class={getStepColor(step.status)}>
              <div class="font-semibold">
                {getStepStatusText(step.status)} {getStepLabel(step.step)}
              </div>
              {step.message && (
                <div class="ml-4 text-gray-700">{step.message}</div>
              )}
              {step.error && (
                <div class="ml-4 font-semibold">{step.error}</div>
              )}
            </div>
          ))}
        </div>

        {/* Discovered Models Summary */}
        {testResults.success && testResults.models && testResults.models.length > 0 && (
          <div class="bg-green-50 rounded-lg p-4 font-mono text-sm text-green-800">
            <div class="font-semibold mb-2">✓ MODELS DISCOVERED: {testResults.models_discovered}</div>
            <div class="space-y-1 ml-4">
              {testResults.models.map((model) => (
                <div key={model.model_key} class="text-xs">
                  • {model.display_name} ({model.model_key})
                  <span class="ml-2 text-gray-600">
                    In: ${model.cost_input}/1M | Out: ${model.cost_output}/1M
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Close Button */}
        <div class="flex justify-end pt-2">
          <button onClick={onClose} class="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </Modal>
  )
}

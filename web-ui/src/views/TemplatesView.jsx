import { useState, useEffect } from 'preact/hooks'
import { api } from '@/api/client'

export default function TemplatesView() {
  const [loading, setLoading] = useState(true)
  const [templates, setTemplates] = useState([])

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString()
  }

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const data = await api.admin.getTemplates()
        setTemplates(data)
      } catch (error) {
        console.error('Failed to load templates:', error)
      } finally {
        setLoading(false)
      }
    }
    loadTemplates()
  }, [])

  if (loading) {
    return (
      <div>
        <h1 class="text-3xl font-bold text-gray-900 mb-8">Prompt Templates</h1>
        <div class="flex justify-center items-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 class="text-3xl font-bold text-gray-900 mb-8">Prompt Templates</h1>

      {/* Templates List */}
      <div class="space-y-4">
        {templates.map((template) => (
          <div key={template.template_id} class="card">
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center space-x-3">
                  <h3 class="text-lg font-semibold text-gray-900">{template.template_name}</h3>
                  <span class="badge badge-info">{template.template_type}</span>
                  {template.is_public && <span class="badge badge-success">Public</span>}
                  {!template.is_active && <span class="badge badge-danger">Inactive</span>}
                </div>

                <p class="text-sm text-gray-600 mt-2">{template.description}</p>

                {/* Variables */}
                {template.variables && (
                  <div class="mt-4">
                    <p class="text-xs font-medium text-gray-700 mb-2">Variables:</p>
                    <div class="flex flex-wrap gap-2">
                      {Object.entries(template.variables).map(([key, value]) => (
                        <span key={key} class="inline-flex items-center px-2 py-1 rounded bg-gray-100 text-xs font-mono text-gray-700">
                          {key}
                          {value.required && <span class="ml-1 text-red-500">*</span>}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div class="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200">
                  <div>
                    <p class="text-xs text-gray-600">Usage Count</p>
                    <p class="text-sm font-medium text-gray-900 mt-1">{template.usage_count || 0}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-600">Success Rate</p>
                    <p class="text-sm font-medium text-gray-900 mt-1">
                      {template.success_rate ? `${template.success_rate}%` : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-600">Max Length</p>
                    <p class="text-sm font-medium text-gray-900 mt-1">
                      {template.output_config?.max_length || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-600">Created</p>
                    <p class="text-sm font-medium text-gray-900 mt-1">{formatDate(template.created_at)}</p>
                  </div>
                </div>

                {/* System Prompt Preview */}
                <details class="mt-4">
                  <summary class="cursor-pointer text-sm font-medium text-primary-600 hover:text-primary-700">
                    View System Prompt
                  </summary>
                  <pre class="mt-2 p-3 bg-gray-50 rounded border border-gray-200 text-xs text-gray-700 overflow-x-auto">{template.system_prompt}</pre>
                </details>

                {/* User Prompt Template Preview */}
                <details class="mt-2">
                  <summary class="cursor-pointer text-sm font-medium text-primary-600 hover:text-primary-700">
                    View User Prompt Template
                  </summary>
                  <pre class="mt-2 p-3 bg-gray-50 rounded border border-gray-200 text-xs text-gray-700 overflow-x-auto">{template.user_prompt_template}</pre>
                </details>
              </div>
            </div>
          </div>
        ))}

        {/* Empty State */}
        {templates.length === 0 && (
          <div class="card text-center py-12">
            <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <h3 class="mt-4 text-lg font-medium text-gray-900">No templates found</h3>
            <p class="mt-2 text-sm text-gray-600">Templates will appear here once they are created.</p>
          </div>
        )}
      </div>
    </div>
  )
}

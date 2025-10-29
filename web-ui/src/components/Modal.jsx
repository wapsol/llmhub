import { useEffect } from 'preact/hooks'

export default function Modal({ isOpen, onClose, title, children, size = 'md' }) {
  // Handle Escape key press
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  // Size classes for modal
  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-6xl'
  }

  return (
    <div class="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        class="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      ></div>

      {/* Modal Container */}
      <div class="flex min-h-screen items-center justify-center p-4">
        {/* Modal Content */}
        <div
          class={`relative bg-white rounded-lg shadow-xl w-full ${sizeClasses[size]} transform transition-all`}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div class="flex items-center justify-between p-6 border-b border-gray-200">
            <h3 class="text-xl font-semibold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              class="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close modal"
            >
              <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          {/* Body */}
          <div class="p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

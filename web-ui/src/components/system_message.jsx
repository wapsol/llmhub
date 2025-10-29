import { useEffect, useState } from 'preact/hooks'

export default function SystemMessage({ type = 'info', message, autoHide = true, duration = 5000 }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (autoHide && message) {
      const timer = setTimeout(() => {
        setVisible(false)
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [autoHide, duration, message])

  if (!visible || !message) return null

  const getClassName = () => {
    switch (type) {
      case 'error':
        return 'system-message-error'
      case 'success':
        return 'system-message-success'
      default:
        return 'system-message'
    }
  }

  return (
    <div class={getClassName()}>
      <div class="flex items-center justify-between">
        <span>{message}</span>
        <button
          onClick={() => setVisible(false)}
          class="ml-2 text-current opacity-70 hover:opacity-100"
        >
          ✕
        </button>
      </div>
    </div>
  )
}

export function useSystemMessage() {
  const [message, setMessage] = useState(null)
  const [type, setType] = useState('info')

  const showMessage = (msg, msgType = 'info') => {
    setMessage(msg)
    setType(msgType)
  }

  const clearMessage = () => {
    setMessage(null)
  }

  return {
    message,
    type,
    showMessage,
    clearMessage
  }
}

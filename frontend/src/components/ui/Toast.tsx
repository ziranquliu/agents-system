import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react'

// ----- Types -----

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: string
  type: ToastType
  message: string
  description?: string
  duration?: number
}

interface ToastContextValue {
  toasts: ToastItem[]
  addToast: (t: Omit<ToastItem, 'id'>) => string
  removeToast: (id: string) => void
  success: (message: string, description?: string) => string
  error: (message: string, description?: string) => string
  warning: (message: string, description?: string) => string
  info: (message: string, description?: string) => string
}

// ----- Context -----

const ToastContext = createContext<ToastContextValue | null>(null)

let _counter = 0
const nextId = () => `toast_${++_counter}_${Date.now()}`

// ----- Provider -----

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    (t: Omit<ToastItem, 'id'>): string => {
      const id = nextId()
      const item: ToastItem = { ...t, id }
      setToasts((prev) => [...prev, item])
      const ms = t.duration ?? 4000
      if (ms > 0) {
        setTimeout(() => removeToast(id), ms)
      }
      return id
    },
    [removeToast],
  )

  const success = useCallback(
    (message: string, description?: string) =>
      addToast({ type: 'success', message, description }),
    [addToast],
  )
  const error = useCallback(
    (message: string, description?: string) =>
      addToast({ type: 'error', message, description }),
    [addToast],
  )
  const warning = useCallback(
    (message: string, description?: string) =>
      addToast({ type: 'warning', message, description }),
    [addToast],
  )
  const info = useCallback(
    (message: string, description?: string) =>
      addToast({ type: 'info', message, description }),
    [addToast],
  )

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, warning, info }}>
      {children}
      {/* Toast 容器 — 固定在右上角 */}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none max-w-sm w-full">
        {toasts.map((t) => (
          <ToastDisplay key={t.id} item={t} onClose={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// ----- Hook -----

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

// ----- Display (internal) -----

const typeStyles: Record<ToastType, { bg: string; border: string; icon: string }> = {
  success: { bg: 'bg-green-50', border: 'border-green-200', icon: '✅' },
  error: { bg: 'bg-red-50', border: 'border-red-200', icon: '❌' },
  warning: { bg: 'bg-amber-50', border: 'border-amber-200', icon: '⚠️' },
  info: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'ℹ️' },
}

function ToastDisplay({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  const style = typeStyles[item.type] || typeStyles.info
  return (
    <div
      className={`pointer-events-auto ${style.bg} ${style.border} border rounded-lg shadow-lg px-4 py-3 flex items-start gap-3 animate-slide-in`}
    >
      <span className="text-base shrink-0 mt-0.5">{style.icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{item.message}</p>
        {item.description && (
          <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
        )}
      </div>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600 text-lg leading-none shrink-0"
      >
        ×
      </button>
    </div>
  )
}

import { useState, useCallback, type ReactNode } from 'react'

interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  confirmVariant?: 'primary' | 'danger'
  showCancel?: boolean
}

interface ConfirmReturn {
  confirm: (opts: ConfirmOptions) => Promise<boolean>
  ConfirmDialog: () => ReactNode
}

interface ConfirmDialogState extends ConfirmOptions {
  visible: boolean
  resolve: ((value: boolean) => void) | null
}

/** 确认对话框 Hook */
export function useConfirm(): ConfirmReturn {
  const [state, setState] = useState<ConfirmDialogState>({
    visible: false,
    message: '',
    resolve: null,
  })

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setState({ ...opts, visible: true, resolve })
    })
  }, [])

  const handleClose = useCallback(
    (result: boolean) => {
      state.resolve?.(result)
      setState((prev) => ({ ...prev, visible: false, resolve: null }))
    },
    [state.resolve],
  )

  const ConfirmDialog = useCallback(() => {
    if (!state.visible) return null
    return (
      <div
        className="fixed inset-0 bg-black/40 z-[9998] flex items-center justify-center"
        onClick={() => handleClose(false)}
      >
        <div
          className="bg-white rounded-2xl p-6 w-full max-w-sm mx-4 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <h3 className="text-base font-semibold text-gray-900 mb-2">
            {state.title || '确认操作'}
          </h3>
          <p className="text-sm text-gray-600 mb-6">{state.message}</p>
          <div className="flex gap-3 justify-end">
            {(state.showCancel ?? true) && (
              <button
                onClick={() => handleClose(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-50 rounded-lg transition-colors"
              >
                {state.cancelText || '取消'}
              </button>
            )}
            <button
              onClick={() => handleClose(true)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors text-white ${
                state.confirmVariant === 'danger'
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {state.confirmText || '确认'}
            </button>
          </div>
        </div>
      </div>
    )
  }, [state, handleClose])

  return { confirm, ConfirmDialog }
}

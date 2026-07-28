import type { ReactNode } from 'react'

interface ErrorBlockProps {
  /** 错误标题 */
  title?: string
  /** 错误描述 */
  message?: string
  /** 重试回调 */
  onRetry?: () => void
  /** 重试按钮文字 */
  retryText?: string
  /** 额外操作区 */
  extra?: ReactNode
  /** 变体：inline（默认嵌入）/ banner（顶部条）/ fullPage（整页） */
  variant?: 'inline' | 'banner' | 'fullPage'
  className?: string
}

const variants = {
  inline: {
    wrapper: 'bg-red-50 border border-red-100 rounded-lg p-4',
    icon: 'text-red-400',
    title: 'text-red-700',
    message: 'text-red-500',
    button: 'text-red-600 hover:bg-red-100',
  },
  banner: {
    wrapper: 'bg-red-50 border-b border-red-100 px-6 py-3',
    icon: 'text-red-400',
    title: 'text-red-700',
    message: 'text-red-500',
    button: 'text-red-600 hover:bg-red-100',
  },
  fullPage: {
    wrapper: 'flex flex-col items-center justify-center min-h-[300px] p-8',
    icon: 'text-red-400',
    title: 'text-red-700',
    message: 'text-red-500',
    button: 'text-red-600 hover:bg-red-50',
  },
}

/** 错误展示组件 */
export default function ErrorBlock({
  title = '出错了',
  message,
  onRetry,
  retryText = '重试',
  extra,
  variant = 'inline',
  className = '',
}: ErrorBlockProps) {
  const s = variants[variant]

  return (
    <div className={`${s.wrapper} ${className}`}>
      <div className={`flex ${variant === 'fullPage' ? 'flex-col items-center text-center' : 'items-start'} gap-3`}>
        <span className={`text-lg ${s.icon} shrink-0`}>⚠️</span>
        <div className={`flex-1 ${variant === 'fullPage' ? 'text-center' : ''}`}>
          <h4 className={`text-sm font-medium ${s.title}`}>{title}</h4>
          {message && <p className={`text-sm mt-1 ${s.message}`}>{message}</p>}
          <div className={`flex gap-2 mt-3 ${variant === 'fullPage' ? 'justify-center' : ''}`}>
            {onRetry && (
              <button onClick={onRetry} className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${s.button}`}>
                {retryText}
              </button>
            )}
            {extra}
          </div>
        </div>
      </div>
    </div>
  )
}

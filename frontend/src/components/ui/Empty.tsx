import type { ReactNode } from 'react'

interface EmptyProps {
  /** 显示的图标（emoji 或 ReactNode） */
  icon?: string | ReactNode
  /** 标题 */
  title?: string
  /** 描述文字 */
  description?: string
  /** 操作按钮 */
  action?: ReactNode
  /** 额外类名 */
  className?: string
}

/** 空状态占位组件 */
export default function Empty({
  icon = '📭',
  title = '暂无数据',
  description,
  action,
  className = '',
}: EmptyProps) {
  return (
    <div className={`flex flex-col items-center justify-center py-16 ${className}`}>
      <div className="text-5xl mb-4">
        {typeof icon === 'string' ? <span>{icon}</span> : icon}
      </div>
      <h3 className="text-base font-medium text-gray-500 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-gray-400 mb-4 max-w-sm text-center">{description}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  )
}

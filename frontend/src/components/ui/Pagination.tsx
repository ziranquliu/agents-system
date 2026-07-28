interface PaginationProps {
  /** 当前页码 (1-indexed) */
  current: number
  /** 总页数 */
  total: number
  /** 总条目数（可选，显示文案） */
  totalItems?: number
  /** 每页条数（可选，配合 totalItems 显示） */
  pageSize?: number
  /** 页码变化回调 */
  onChange: (page: number) => void
  /** 额外类名 */
  className?: string
  /** 显示的页码按钮数（含省略号） */
  maxVisible?: number
}

/**
 * 通用分页组件
 *
 * 用法：
 *  <Pagination current={page} total={totalPages} onChange={setPage} />
 */
export default function Pagination({
  current,
  total,
  totalItems,
  pageSize,
  onChange,
  className = '',
  maxVisible = 7,
}: PaginationProps) {
  if (total <= 1) return null

  // 生成可见页码
  const getPages = (): (number | 'ellipsis')[] => {
    if (total <= maxVisible) {
      return Array.from({ length: total }, (_, i) => i + 1)
    }

    const pages: (number | 'ellipsis')[] = []
    const half = Math.floor((maxVisible - 1) / 2)
    let start = current - half
    let end = current + half

    if (start < 1) {
      start = 1
      end = maxVisible - 1
    }
    if (end > total) {
      end = total
      start = total - maxVisible + 2
    }

    // 首页
    if (start > 2) {
      pages.push(1, 'ellipsis')
    } else if (start === 2) {
      pages.push(1)
    }

    // 中间页
    for (let i = start; i <= end; i++) {
      if (i >= 1 && i <= total) pages.push(i)
    }

    // 末页
    if (end < total - 1) {
      pages.push('ellipsis', total)
    } else if (end === total - 1) {
      pages.push(total)
    }

    return pages
  }

  const pages = getPages()
  const from = totalItems && pageSize ? (current - 1) * pageSize + 1 : undefined
  const to = totalItems && pageSize ? Math.min(current * pageSize, totalItems) : undefined

  const btnBase =
    'px-3 py-1.5 text-sm border rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed'
  const btnActive = 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
  const btnInactive = 'border-gray-200 text-gray-600 hover:bg-gray-50'

  return (
    <div className={`flex items-center justify-between gap-4 ${className}`}>
      {/* 信息 */}
      {totalItems !== undefined && (
        <span className="text-sm text-gray-500">
          共 {totalItems} 条
          {from && to ? `，第 ${from}-${to} 条` : ''}
        </span>
      )}

      {/* 页码 */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(current - 1)}
          disabled={current <= 1}
          className={`${btnBase} ${btnInactive}`}
        >
          上一页
        </button>

        {pages.map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`e${i}`} className="px-2 text-gray-400 text-sm">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`${btnBase} ${p === current ? btnActive : btnInactive}`}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onChange(current + 1)}
          disabled={current >= total}
          className={`${btnBase} ${btnInactive}`}
        >
          下一页
        </button>
      </div>
    </div>
  )
}

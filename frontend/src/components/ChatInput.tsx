/**
 * 流式聊天输入框组件
 */
import React, { useState, useRef, useEffect } from 'react'
import { Send, StopCircle } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  onCancel?: () => void
  disabled?: boolean
  isLoading?: boolean
  placeholder?: string
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onCancel,
  disabled = false,
  isLoading = false,
  placeholder = '输入消息...',
}) => {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  // 自动调整高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || disabled) return
    onSend(input.trim())
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }
  
  return (
    <form onSubmit={handleSubmit} className="border-t bg-white p-4">
      <div className="flex gap-2 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="w-full resize-none rounded-lg border border-gray-200 px-4 py-3 pr-12 
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:bg-gray-50 disabled:text-gray-500"
            style={{ minHeight: '52px' }}
          />
          {isLoading && (
            <button
              type="button"
              onClick={onCancel}
              className="absolute right-3 bottom-3 p-1.5 rounded-full bg-red-500 text-white 
                         hover:bg-red-600 transition-colors animate-pulse"
              title="停止生成"
            >
              <StopCircle size={16} />
            </button>
          )}
        </div>
        <button
          type="submit"
          disabled={!input.trim() || disabled}
          className="p-3 rounded-lg bg-blue-500 text-white hover:bg-blue-600 
                     disabled:bg-gray-300 disabled:cursor-not-allowed
                     transition-all duration-200 flex items-center justify-center"
          title="发送"
        >
          <Send size={18} />
        </button>
      </div>
      <p className="text-xs text-gray-400 mt-2">
        按 Enter 发送，Shift + Enter 换行
      </p>
    </form>
  )
}

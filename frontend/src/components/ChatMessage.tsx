/**
 * 流式聊天消息组件
 */
import React, { useEffect, useRef } from 'react'
import { User, Bot, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: Date
  isStreaming?: boolean
  toolName?: string
}

interface ChatMessageItemProps {
  message: ChatMessage
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message }) => {
  const bottomRef = useRef<HTMLDivElement>(null)
  
  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [message])
  
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const isTool = message.role === 'tool'
  
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} mb-4`}>
      {/* 头像 */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
        ${isUser ? 'bg-blue-500' : isAssistant ? 'bg-green-500' : 'bg-gray-400'}`}>
        {isUser && <User size={16} className="text-white" />}
        {isAssistant && <Bot size={16} className="text-white" />}
        {isTool && <Loader2 size={16} className="text-white animate-spin" />}
      </div>
      
      {/* 消息内容 */}
      <div className={`max-w-[70%] rounded-lg px-4 py-3
        ${isUser 
          ? 'bg-blue-500 text-white' 
          : isAssistant 
            ? 'bg-gray-100 text-gray-800' 
            : 'bg-yellow-50 text-gray-600 border border-yellow-200'}`}>
        
        {isTool && message.toolName && (
          <div className="text-xs font-medium mb-1 opacity-75">
            🔧 {message.toolName}
          </div>
        )}
        
        {isAssistant ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown
              components={{
                code: ({ children, className }) => {
                  const isInline = !className
                  return isInline ? (
                    <code className="bg-gray-200 rounded px-1 text-sm">{children}</code>
                  ) : (
                    <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto">
                      <code className={className}>{children}</code>
                    </pre>
                  )
                },
                pre: ({ children }) => <>{children}</>,
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
            )}
          </div>
        ) : (
          <div>{message.content}</div>
        )}
        
        <div className={`text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-gray-400'}`}>
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
      
      <div ref={bottomRef} />
    </div>
  )
}

interface ChatMessagesListProps {
  messages: ChatMessage[]
}

export const ChatMessagesList: React.FC<ChatMessagesListProps> = ({ messages }) => {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <Bot size={48} className="mb-4 opacity-30" />
        <p>开始对话</p>
        <p className="text-sm mt-2">输入消息与智能体开始交流</p>
      </div>
    )
  }
  
  return (
    <div className="px-6 py-4">
      {messages.map((msg) => (
        <ChatMessageItem key={msg.id} message={msg} />
      ))}
    </div>
  )
}

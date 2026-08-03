/**
 * 流式对话页面
 */
import React, { useState, useRef, useEffect } from 'react'
import { StopCircle, Bot } from 'lucide-react'
import { useWebSocketChat } from '../hooks/useWebSocket'
import { ChatInput } from '../components/ChatInput'
import { ChatMessagesList, ChatMessage } from '../components/ChatMessage'

interface StreamingChatPageProps {
  sessionId?: string
  agentId?: string
}

const StreamingChatPage: React.FC<StreamingChatPageProps> = ({ 
  sessionId = 'default-session',
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [currentToken, setCurrentToken] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const {
    sendMessage,
    cancelMessage,
    isConnected,
    attemptReconnect,
  } = useWebSocketChat({
    sessionId,
    onToken: (token: string) => {
      setCurrentToken(prev => prev + token)
    },
    onComplete: (message) => {
      if (currentToken) {
        setMessages(prev => [...prev, {
          id: message.message_id || `msg-${Date.now()}`,
          role: 'assistant',
          content: currentToken,
          timestamp: new Date(),
          isStreaming: false,
        }])
      }
      setCurrentToken('')
    },
    onError: (error: string) => {
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `错误: ${error}`,
        timestamp: new Date(),
      }])
    },
    onToolCall: (tool: string) => {
      setMessages(prev => [...prev, {
        id: `tool-${Date.now()}`,
        role: 'tool',
        content: `调用工具: ${tool}`,
        toolName: tool,
        timestamp: new Date(),
      }])
    },
  })
  
  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentToken])
  
  const handleSend = (content: string) => {
    // 添加用户消息
    setMessages(prev => [...prev, {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    }])
    
    // 发送消息并开始流式接收
    sendMessage(content)
  }
  
  const handleCancel = () => {
    cancelMessage()
    setCurrentToken('')
  }
  
  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 头部 */}
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-gray-900">AI 助手</h1>
            <p className="text-sm text-gray-500">
              {isConnected ? '在线' : '连接中...'}
            </p>
          </div>
        </div>
        
        {!isConnected && (
          <button
            onClick={attemptReconnect}
            className="px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            重连
          </button>
        )}
      </div>
      
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto">
        <ChatMessagesList messages={[...messages]} />
        
        {/* 当前流式输出 */}
        {currentToken && (
          <div className="px-6 py-4">
            <div className="max-w-3xl mx-auto bg-white rounded-lg shadow-sm p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                  <Bot size={14} className="text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-gray-800 whitespace-pre-wrap">
                    {currentToken}
                    <span className="inline-block w-0.5 h-4 bg-blue-500 animate-pulse ml-0.5" />
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* 输入框 */}
      <div className="bg-white border-t p-4">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSend={handleSend}
            onCancel={handleCancel}
            isLoading={!!currentToken}
            disabled={!isConnected}
            placeholder={isConnected ? "输入消息，按 Enter 发送..." : "连接断开，请点击重连"}
          />
          
          {currentToken && (
            <div className="mt-2 flex justify-end">
              <button
                onClick={handleCancel}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <StopCircle size={14} />
                停止生成
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StreamingChatPage

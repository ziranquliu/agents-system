/**
 * WebSocket对话Hook
 * 封装WebSocket连接和消息处理逻辑
 */
import { useEffect, useRef, useCallback } from 'react'
import { useWSStore, WSMessage } from '../stores/wsStore'

interface UseWebSocketChatOptions {
  sessionId: string
  onToken?: (token: string) => void
  onComplete?: (message: WSMessage) => void
  onError?: (error: string) => void
  onToolCall?: (tool: string, args: Record<string, any>) => void
}

export function useWebSocketChat({
  sessionId,
  onToken,
  onComplete,
  onError,
  onToolCall,
}: UseWebSocketChatOptions) {
  const {
    connect,
    disconnect,
    send,
    cancel,
    getConnection,
    setOnMessage,
    setOnError,
  } = useWSStore()
  
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const shouldReconnectRef = useRef(true)
  
  // 设置消息回调
  useEffect(() => {
    setOnMessage((sid: string, message: WSMessage) => {
      if (sid !== sessionId) return
      
      switch (message.type) {
        case 'token':
          onToken?.(message.token || '')
          break
        case 'done':
          onComplete?.(message)
          break
        case 'error':
          onError?.(message.error || 'Unknown error')
          break
        case 'tool_call':
          onToolCall?.(message.tool || '', message.args || {})
          break
      }
    })
    
    setOnError((sid: string, error: string) => {
      if (sid === sessionId) {
        onError?.(error)
      }
    })
  }, [sessionId, onToken, onComplete, onError, onToolCall, setOnMessage, setOnError])
  
  // 建立连接
  useEffect(() => {
    shouldReconnectRef.current = true
    
    connect(sessionId)
    
    return () => {
      shouldReconnectRef.current = false
      disconnect(sessionId)
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [sessionId])
  
  // 发送消息
  const sendMessage = useCallback((content: string, metadata?: Record<string, any>) => {
    send(sessionId, {
      type: 'message',
      content,
      ...(metadata || {}),
    })
  }, [sessionId, send])
  
  // 取消对话
  const cancelMessage = useCallback(() => {
    cancel(sessionId)
  }, [sessionId, cancel])
  
  // 检查连接状态
  const isConnected = useCallback(() => {
    const conn = getConnection(sessionId)
    return conn?.isConnected || false
  }, [sessionId, getConnection])
  
  // 自动重连
  const attemptReconnect = useCallback(() => {
    if (!shouldReconnectRef.current) return
    
    reconnectTimeoutRef.current = setTimeout(() => {
      if (shouldReconnectRef.current) {
        connect(sessionId)
      }
    }, 2000)
  }, [sessionId, connect])
  
  return {
    sendMessage,
    cancelMessage,
    isConnected,
    attemptReconnect,
  }
}

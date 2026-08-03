/**
 * WebSocket对话Hook
 * 封装WebSocket连接和消息处理逻辑
 * 同时兼容两套调用风格：
 *  - StreamingChatPage: { sessionId, onToken, onComplete }
 *  - ConversationDetail: { conversationId, token, autoConnect, onChunk, onDone }
 */
import { useEffect, useRef, useCallback } from 'react'
import { useWSStore, WSMessage } from '../stores/wsStore'

export interface UseWebSocketChatOptions {
  sessionId?: string
  /** 兼容别名：会话 ID（与 sessionId 等价） */
  conversationId?: string
  /** 鉴权 token（随消息携带） */
  token?: string
  /** 是否自动连接，默认 true */
  autoConnect?: boolean
  onToken?: (token: string) => void
  /** 兼容别名：流式增量文本 */
  onChunk?: (text: string) => void
  onComplete?: (message: WSMessage) => void
  /** 兼容别名：完成回调（传入完整文本） */
  onDone?: (fullText: string) => void
  onError?: (error: string) => void
  onToolCall?: (tool: string, args: Record<string, any>) => void
}

export function useWebSocketChat(options: UseWebSocketChatOptions) {
  const sessionId = options.sessionId || options.conversationId || 'default-session'
  const { onToken, onChunk, onComplete, onDone, onError, onToolCall } = options

  const {
    connect,
    disconnect,
    send,
    cancel,
    setOnMessage,
    setOnError,
  } = useWSStore()

  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const shouldReconnectRef = useRef(true)
  const streamTextRef = useRef('')

  // 反应式连接状态（从 store 订阅，替换原“函数式 isConnected”）
  const conn = useWSStore((s) => s.connections.get(sessionId))
  const isConnected = !!conn?.isConnected
  const isConnecting = !!conn?.isConnecting
  const lastError = conn?.lastError ?? null
  const status: 'connected' | 'connecting' | 'disconnected' | 'error' =
    isConnected ? 'connected' : isConnecting ? 'connecting' : lastError ? 'error' : 'disconnected'

  // 设置消息回调
  useEffect(() => {
    setOnMessage((sid: string, message: WSMessage) => {
      if (sid !== sessionId) return

      switch (message.type) {
        case 'token': {
          const text = message.token || ''
          onToken?.(text)
          if (onChunk) {
            streamTextRef.current += text
            onChunk(streamTextRef.current)
          }
          break
        }
        case 'done': {
          onComplete?.(message)
          if (onDone) {
            onDone(streamTextRef.current || message.content || '')
            streamTextRef.current = ''
          }
          break
        }
        case 'error':
          onError?.(message.error || 'Unknown error')
          streamTextRef.current = ''
          break
        case 'tool_call':
          onToolCall?.(message.tool || '', message.args || {})
          break
      }
    })

    setOnError((sid: string, error: string) => {
      if (sid === sessionId) {
        onError?.(error)
        streamTextRef.current = ''
      }
    })
  }, [sessionId, onToken, onChunk, onComplete, onDone, onError, onToolCall, setOnMessage, setOnError])

  // 建立连接
  useEffect(() => {
    const autoConnect = options.autoConnect ?? true
    shouldReconnectRef.current = true

    if (autoConnect) {
      connect(sessionId)
    }

    return () => {
      shouldReconnectRef.current = false
      disconnect(sessionId)

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [sessionId, options.autoConnect, connect, disconnect])

  // 发送消息
  const sendMessage = useCallback((content: string, metadata?: Record<string, any>) => {
    send(sessionId, {
      type: 'message',
      content,
      ...(metadata || {}),
    })
  }, [sessionId, send])

  // 兼容别名：send(content, model?)
  const sendAlias = useCallback((content: string, model?: string) => {
    send(sessionId, { type: 'message', content, model })
  }, [sessionId, send])

  // 取消对话
  const cancelMessage = useCallback(() => {
    cancel(sessionId)
  }, [sessionId, cancel])

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
    isConnected, // 反应式布尔，可直接用于 JSX 条件
    attemptReconnect,
    // 兼容 ConversationDetail 接口
    status,
    connect: (sid?: string) => connect(sid || sessionId),
    disconnect: (sid?: string) => disconnect(sid || sessionId),
    send: sendAlias,
    conversationId: sessionId,
  }
}

// 导出别名，兼容不同命名
export const useWebSocket = useWebSocketChat

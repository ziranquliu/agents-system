import { useCallback, useEffect, useRef, useState } from 'react'

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketOptions {
  conversationId: string
  token: string
  autoConnect?: boolean
  onChunk?: (text: string) => void
  onDone?: (fullText: string, model: string) => void
  onError?: (msg: string) => void
}

interface UseWebSocketReturn {
  send: (content: string, model?: string) => void
  status: WsStatus
  connect: () => void
  disconnect: () => void
  reconnect: () => void
}

const RECONNECT_DELAY = 3000
const PING_INTERVAL = 25000

export function useWebSocket({
  conversationId,
  token,
  autoConnect = true,
  onChunk,
  onDone,
  onError,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  // 用 ref 保存回调，避免每次渲染导致 connect 重新创建
  const onChunkRef = useRef(onChunk)
  const onDoneRef = useRef(onDone)
  const onErrorRef = useRef(onError)
  onChunkRef.current = onChunk
  onDoneRef.current = onDone
  onErrorRef.current = onError

  const clearTimers = useCallback(() => {
    if (pingRef.current) {
      clearInterval(pingRef.current)
      pingRef.current = null
    }
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current)
      reconnectRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!conversationId) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    // 后端 WebSocket 注册在 app 级别 (/ws/chat/{id})，不在 /api/v1 下
    const baseUrl = import.meta.env.VITE_WS_URL || `${protocol}://localhost:8000`
    const url = `${baseUrl}/ws/chat/${conversationId}${token ? `?token=${token}` : ''}`

    try {
      // 如果已有连接，先关闭
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }

      const ws = new WebSocket(url)
      wsRef.current = ws
      setStatus('connecting')

      ws.onopen = () => {
        if (!mountedRef.current) { ws.close(); return }
        setStatus('connected')
        // 心跳
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, PING_INTERVAL)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          switch (data.type) {
            case 'chunk':
              onChunkRef.current?.(data.content || '')
              break
            case 'done':
              onDoneRef.current?.(data.content || '', data.model || '')
              break
            case 'error':
              onErrorRef.current?.(data.content || '未知错误')
              break
          }
        } catch {
          // skip malformed messages
        }
      }

      ws.onclose = () => {
        clearTimers()
        if (!mountedRef.current) return
        setStatus('disconnected')
        // 自动重连
        reconnectRef.current = setTimeout(connect, RECONNECT_DELAY)
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setStatus('error')
        ws.close()
      }
    } catch {
      setStatus('error')
    }
  }, [conversationId, token, clearTimers])

  const disconnect = useCallback(() => {
    clearTimers()
    if (wsRef.current) {
      wsRef.current.onclose = null // 阻止自动重连
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('disconnected')
  }, [clearTimers])

  const reconnect = useCallback(() => {
    disconnect()
    setTimeout(connect, 100)
  }, [disconnect, connect])

  const send = useCallback((content: string, model = 'gpt-4o-mini') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'message', content, model }))
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    if (autoConnect) {
      connect()
    }
    return () => {
      mountedRef.current = false
      clearTimers()
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, clearTimers, autoConnect])

  return { send, status, connect, disconnect, reconnect }
}

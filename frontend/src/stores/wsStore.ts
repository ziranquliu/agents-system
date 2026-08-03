/**
 * WebSocket连接管理Store
 * 管理所有WebSocket连接的建立、维护和消息处理
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type WSMessageType = 
  | 'message'      // 用户消息
  | 'token'        // 流式token
  | 'tool_call'    // 工具调用
  | 'tool_result'  // 工具结果
  | 'done'         // 完成
  | 'error'        // 错误
  | 'cancel'       // 取消

export interface WSMessage {
  type: WSMessageType
  content?: string
  token?: string
  tool?: string
  args?: Record<string, any>
  model?: string
  message_id?: string
  error?: string
  latency_ms?: number
  timestamp?: string
}

export interface WSConnection {
  sessionId: string
  ws: WebSocket | null
  isConnected: boolean
  isConnecting: boolean
  reconnectAttempts: number
  lastError: string | null
  messages: WSMessage[]
  isStreaming: boolean
  isManualDisconnect: boolean
}

interface WSState {
  connections: Map<string, WSConnection>
  onMessage: ((sessionId: string, message: WSMessage) => void) | null
  onError: ((sessionId: string, error: string) => void) | null
  
  // Actions
  connect: (sessionId: string, baseUrl?: string) => Promise<void>
  disconnect: (sessionId: string) => void
  send: (sessionId: string, message: WSMessage) => void
  cancel: (sessionId: string) => void
  clearMessages: (sessionId: string) => void
  setOnMessage: (callback: ((sessionId: string, message: WSMessage) => void) | null) => void
  setOnError: (callback: ((sessionId: string, error: string) => void) | null) => void
  getConnection: (sessionId: string) => WSConnection | undefined
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const useWSStore = create<WSState>()(
  persist(
    (set, get) => ({
      connections: new Map(),
      onMessage: null,
      onError: null,
      
      connect: async (sessionId: string, baseUrl?: string) => {
        const url = `${baseUrl || DEFAULT_BASE_URL.replace('http', 'ws').replace('https', 'wss')}/ws/chat/${sessionId}?token=${encodeURIComponent(localStorage.getItem('token') || '')}`
        
        set((state) => ({
          connections: new Map(state.connections).set(sessionId, {
            sessionId,
            ws: null,
            isConnected: false,
            isConnecting: true,
            reconnectAttempts: 0,
            lastError: null,
            messages: [],
            isStreaming: false,
            isManualDisconnect: false,
          })
        }))
        
        try {
          const ws = new WebSocket(url)
          
          ws.onopen = () => {
            set((state) => {
              const connections = new Map(state.connections)
              const conn = connections.get(sessionId)!
              connections.set(sessionId, {
                ...conn,
                ws,
                isConnected: true,
                isConnecting: false,
                reconnectAttempts: 0,
              })
              return { connections }
            })
          }
          
          ws.onmessage = (event) => {
            try {
              const message: WSMessage = JSON.parse(event.data)
              
              set((state) => {
                const connections = new Map(state.connections)
                const conn = connections.get(sessionId)!
                connections.set(sessionId, {
                  ...conn,
                  messages: [...conn.messages, message],
                  isStreaming: message.type === 'token',
                })
                return { connections }
              })
              
              // 通知回调
              const { onMessage } = get()
              if (onMessage) {
                onMessage(sessionId, message)
              }
            } catch (error) {
              console.error('[WS] Failed to parse message:', error)
            }
          }
          
          ws.onerror = (event) => {
            console.error('[WS] Connection error:', event)
            
            set((state) => {
              const connections = new Map(state.connections)
              const conn = connections.get(sessionId)!
              connections.set(sessionId, {
                ...conn,
                lastError: 'WebSocket error occurred',
              })
              return { connections }
            })
            
            const { onError } = get()
            if (onError) {
              onError(sessionId, 'WebSocket connection error')
            }
          }
          
          ws.onclose = (event) => {
            console.log('[WS] Connection closed:', event.code, event.reason)
            
            set((state) => {
              const connections = new Map(state.connections)
              const conn = connections.get(sessionId)!
              connections.set(sessionId, {
                ...conn,
                ws: null,
                isConnected: false,
                isConnecting: false,
              })
              return { connections }
            })
            
            // 自动重连逻辑
            const { connections } = get()
            const currentConn = connections.get(sessionId)
            if (currentConn && !currentConn.isManualDisconnect && event.code !== 1000) {
              setTimeout(() => {
                get().connect(sessionId, baseUrl)
              }, 1000 * Math.min(currentConn.reconnectAttempts + 1, 5))
            }
          }
          
          // 保存ws引用
          set((state) => {
            const connections = new Map(state.connections)
            const conn = connections.get(sessionId)!
            connections.set(sessionId, { ...conn, ws })
            return { connections }
          })
          
        } catch (error) {
          console.error('[WS] Failed to connect:', error)
          
          set((state) => {
            const connections = new Map(state.connections)
            const conn = connections.get(sessionId)!
            connections.set(sessionId, {
              ...conn,
              isConnecting: false,
              lastError: error instanceof Error ? error.message : 'Connection failed',
            })
            return { connections }
          })
          
          const { onError } = get()
          if (onError) {
            onError(sessionId, error instanceof Error ? error.message : 'Connection failed')
          }
        }
      },
      
      disconnect: (sessionId: string) => {
        const ws = get().getConnection(sessionId)?.ws
        if (ws) {
          ws.close(1000, 'Manual disconnect')
        }
        
        set((state) => {
          const connections = new Map(state.connections)
          const conn = connections.get(sessionId)!
          connections.set(sessionId, {
            ...conn,
            ws: null,
            isConnected: false,
            isConnecting: false,
            isManualDisconnect: true,
          })
          return { connections }
        })
      },
      
      send: (sessionId: string, message: WSMessage) => {
        const conn = get().getConnection(sessionId)
        if (!conn?.ws || conn.ws.readyState !== WebSocket.OPEN) {
          console.error('[WS] Cannot send: connection not open')
          return
        }
        
        conn.ws.send(JSON.stringify(message))
      },
      
      cancel: (sessionId: string) => {
        get().send(sessionId, { type: 'cancel' })
      },
      
      clearMessages: (sessionId: string) => {
        set((state) => {
          const connections = new Map(state.connections)
          const conn = connections.get(sessionId)!
          connections.set(sessionId, {
            ...conn,
            messages: [],
          })
          return { connections }
        })
      },
      
      setOnMessage: (callback) => {
        set({ onMessage: callback })
      },
      
      setOnError: (callback) => {
        set({ onError: callback })
      },
      
      getConnection: (sessionId: string) => {
        return get().connections.get(sessionId)
      },
    }),
    {
      name: 'ws-store',
      partialize: () => ({
        // 不持久化连接状态
      }),
    }
  )
)

import client from './client'

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
}

export interface ChatCompletionResponse {
  id: string
  model: string
  choices: {
    index: number
    message: { role: string; content: string }
    finish_reason: string
  }[]
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  created: number
}

/** 非流式对话补全 */
export async function chatCompletions(data: {
  model: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
}) {
  const { data: res } = await client.post<ChatCompletionResponse>('/chat/completions', data)
  return res
}

/** SSE 流式对话补全
 *  返回一个 abort 函数用于取消请求 */
export function chatStream(
  data: {
    model: string
    messages: ChatMessage[]
    temperature?: number
    max_tokens?: number
  },
  callbacks: {
    onChunk: (text: string) => void
    onDone: (fullText: string) => void
    onError: (err: Error) => void
  },
): () => void {
  const token = localStorage.getItem('token')
  const controller = new AbortController()
  let fullText = ''

  fetch('/api/v1/chat/completions?stream=true', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errBody = await response.text().catch(() => '')
        throw new Error(errBody || `HTTP ${response.status}`)
      }
      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice(6)
          if (jsonStr === '[DONE]') break

          try {
            const chunk = JSON.parse(jsonStr)
            const content = chunk?.choices?.[0]?.delta?.content || ''
            if (content) {
              fullText += content
              callbacks.onChunk(content)
            }
          } catch {
            // skip malformed chunk
          }
        }
      }

      // 处理 buffer 中剩余数据
      if (buffer.trim().startsWith('data: ')) {
        const jsonStr = buffer.trim().slice(6)
        if (jsonStr !== '[DONE]') {
          try {
            const chunk = JSON.parse(jsonStr)
            const content = chunk?.choices?.[0]?.delta?.content || ''
            if (content) {
              fullText += content
              callbacks.onChunk(content)
            }
          } catch { /* skip */ }
        }
      }

      callbacks.onDone(fullText)
    })
    .catch((err) => {
      if (err.name === 'AbortError') return
      callbacks.onError(err)
    })

  return () => controller.abort()
}

import axios from 'axios'

/**
 * 统一 API 客户端
 * - 自动注入 JWT Bearer Token
 * - 401 自动登出跳转
 * - 统一响应格式: { code: number, data: T, message: string, request_id: string, timestamp: number }
 */

// 统一存储 key — 兼容两种写法
function getToken(): string | null {
  return localStorage.getItem('access_token') || localStorage.getItem('token')
}

function clearAuth() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  window.location.href = '/login'
}

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 — 自动带上 Token
client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 — 统一处理错误
client.interceptors.response.use(
  (response) => {
    // 解包统一响应: { code, data, message } → 返回 data 层
    const body = response.data
    if (body && typeof body.code === 'number') {
      if (body.code !== 0) {
        // 业务错误: 在 response 上附加 error_info
        return Promise.reject({
          message: body.message || '请求失败',
          error_code: body.error_code,
          request_id: body.request_id,
          code: body.code,
        })
      }
      // 成功: 替换 response.data 为 data 字段，方便业务层直接使用
      response.data = body.data
    }
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      clearAuth()
    }
    return Promise.reject(error)
  },
)

export default client

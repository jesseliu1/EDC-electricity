import axios from 'axios'
import type { AxiosRequestConfig, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000
})

interface RequestMeta {
  skipErrorMessage?: boolean
}

interface ExtendedAxiosRequestConfig extends AxiosRequestConfig {
  meta?: RequestMeta
}

let lastNetworkMessageAt = 0

function shouldMuteNetworkMessage() {
  const now = Date.now()
  if (now - lastNetworkMessageAt < 4000) {
    return true
  }
  lastNetworkMessageAt = now
  return false
}

function getRequestMeta(config?: InternalAxiosRequestConfig | ExtendedAxiosRequestConfig): RequestMeta {
  const requestConfig = config as ExtendedAxiosRequestConfig | undefined
  return requestConfig?.meta || {}
}

function resolveErrorMessage(error: AxiosError<{ message?: string; detail?: string }>) {
  const payload = error.response?.data
  if (typeof payload?.message === 'string' && payload.message.trim()) {
    return payload.message
  }
  if (typeof payload?.detail === 'string' && payload.detail.trim()) {
    return payload.detail
  }
  return '请求失败'
}

instance.interceptors.response.use(
  response => response.data,
  (error: AxiosError<{ message?: string }>) => {
    const meta = getRequestMeta(error.config)
    if (meta.skipErrorMessage) {
      return Promise.reject(error)
    }

    if (!error.response) {
      if (!shouldMuteNetworkMessage()) {
        ElMessage.warning(
          error.code === 'ECONNABORTED'
            ? '请求超时，请检查后端服务状态或接口性能'
            : '后端服务未连接，请检查网络或服务状态'
        )
      }
      return Promise.reject(error)
    }

    ElMessage.error(resolveErrorMessage(error))
    return Promise.reject(error)
  }
)

interface HttpClient {
  get<T>(url: string, config?: ExtendedAxiosRequestConfig): Promise<T>
  post<T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig): Promise<T>
  patch<T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig): Promise<T>
  put<T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig): Promise<T>
  delete<T>(url: string, config?: ExtendedAxiosRequestConfig): Promise<T>
}

const client: HttpClient = {
  get: <T>(url: string, config?: ExtendedAxiosRequestConfig) =>
    instance.get(url, config) as unknown as Promise<T>,
  post: <T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig) =>
    instance.post(url, data, config) as unknown as Promise<T>,
  patch: <T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig) =>
    instance.patch(url, data, config) as unknown as Promise<T>,
  put: <T>(url: string, data?: unknown, config?: ExtendedAxiosRequestConfig) =>
    instance.put(url, data, config) as unknown as Promise<T>,
  delete: <T>(url: string, config?: ExtendedAxiosRequestConfig) =>
    instance.delete(url, config) as unknown as Promise<T>
}

export { client }

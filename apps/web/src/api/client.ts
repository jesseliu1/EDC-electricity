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

instance.interceptors.response.use(
  response => response.data,
  (error: AxiosError<{ message?: string }>) => {
    const meta = getRequestMeta(error.config)
    if (meta.skipErrorMessage) {
      return Promise.reject(error)
    }

    if (!error.response) {
      if (!shouldMuteNetworkMessage()) {
        ElMessage.warning('后端服务未连接，当前页面将回退为本地 Mock 数据')
      }
      return Promise.reject(error)
    }

    ElMessage.error(error.response.data?.message || '请求失败')
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

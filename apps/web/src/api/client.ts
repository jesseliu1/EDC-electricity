import axios from 'axios'
import type { AxiosRequestConfig, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { isShowtimeMode } from '@/utils/showtime'

const REQUEST_ID_HEADER = 'X-Request-ID'
const DIAGNOSTIC_BUFFER_LIMIT = 50
const SLOW_REQUEST_THRESHOLD_MS = 4000

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000
})

interface RequestMeta {
  skipErrorMessage?: boolean
  operation?: string
}

interface ExtendedAxiosRequestConfig extends AxiosRequestConfig {
  meta?: RequestMeta
}

interface RequestDiagnosticMeta {
  requestId: string
  startedAtMs: number
  startedAtIso: string
  route: string
  method: string
  url: string
  operation?: string
}

interface ExtendedInternalAxiosRequestConfig extends InternalAxiosRequestConfig {
  meta?: RequestMeta
  diagnosticMeta?: RequestDiagnosticMeta
}

interface NetworkDiagnosticRecord {
  requestId: string
  route: string
  method: string
  url: string
  startedAt: string
  durationMs: number
  outcome: 'slow' | 'timeout' | 'network_error' | 'http_error'
  statusCode?: number
  errorCode?: string
  operation?: string
}

declare global {
  interface Window {
    __ASNS_NETWORK_DIAGNOSTICS__?: NetworkDiagnosticRecord[]
  }
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

function createRequestId() {
  if (typeof window !== 'undefined' && typeof window.crypto?.randomUUID === 'function') {
    return window.crypto.randomUUID().replace(/-/g, '')
  }
  return `${Date.now()}${Math.random().toString(16).slice(2, 10)}`
}

function resolveCurrentRoute() {
  if (typeof window === 'undefined') {
    return ''
  }
  return `${window.location.pathname}${window.location.search}`
}

function pushDiagnosticRecord(record: NetworkDiagnosticRecord) {
  if (typeof window !== 'undefined') {
    const records = window.__ASNS_NETWORK_DIAGNOSTICS__ || []
    records.push(record)
    if (records.length > DIAGNOSTIC_BUFFER_LIMIT) {
      records.splice(0, records.length - DIAGNOSTIC_BUFFER_LIMIT)
    }
    window.__ASNS_NETWORK_DIAGNOSTICS__ = records
  }
  console.warn('[network-diagnostic]', record)
}

function buildDiagnosticRecord(
  diagnosticMeta: RequestDiagnosticMeta | undefined,
  outcome: NetworkDiagnosticRecord['outcome'],
  extra?: Pick<NetworkDiagnosticRecord, 'statusCode' | 'errorCode'>
): NetworkDiagnosticRecord | null {
  if (!diagnosticMeta) {
    return null
  }
  return {
    requestId: diagnosticMeta.requestId,
    route: diagnosticMeta.route,
    method: diagnosticMeta.method,
    url: diagnosticMeta.url,
    startedAt: diagnosticMeta.startedAtIso,
    durationMs: Date.now() - diagnosticMeta.startedAtMs,
    outcome,
    statusCode: extra?.statusCode,
    errorCode: extra?.errorCode,
    operation: diagnosticMeta.operation
  }
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

instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const requestConfig = config as ExtendedInternalAxiosRequestConfig
  const headers = config.headers
  const requestId = createRequestId()
  requestConfig.diagnosticMeta = {
    requestId,
    startedAtMs: Date.now(),
    startedAtIso: new Date().toISOString(),
    route: resolveCurrentRoute(),
    method: String(config.method || 'get').toUpperCase(),
    url: String(config.url || ''),
    operation: requestConfig.meta?.operation
  }
  if (isShowtimeMode()) {
    if (typeof headers.set === 'function') {
      headers.set('X-Showtime', 'true')
    } else {
      ;(config.headers as Record<string, string>)['X-Showtime'] = 'true'
    }
  } else {
    if (typeof headers.delete === 'function') {
      headers.delete('X-Showtime')
    } else {
      delete (config.headers as Record<string, string>)['X-Showtime']
    }
  }
  if (typeof headers.set === 'function') {
    headers.set(REQUEST_ID_HEADER, requestId)
  } else {
    ;(config.headers as Record<string, string>)[REQUEST_ID_HEADER] = requestId
  }
  return config
})

instance.interceptors.response.use(
  response => {
    const requestConfig = response.config as ExtendedInternalAxiosRequestConfig
    const diagnosticRecord = buildDiagnosticRecord(requestConfig.diagnosticMeta, 'slow')
    if (diagnosticRecord && diagnosticRecord.durationMs >= SLOW_REQUEST_THRESHOLD_MS) {
      pushDiagnosticRecord(diagnosticRecord)
    }
    return response.data
  },
  (error: AxiosError<{ message?: string }>) => {
    const meta = getRequestMeta(error.config)
    const requestConfig = error.config as ExtendedInternalAxiosRequestConfig | undefined
    const diagnosticMeta = requestConfig?.diagnosticMeta

    if (!error.response) {
      const diagnosticRecord = buildDiagnosticRecord(
        diagnosticMeta,
        error.code === 'ECONNABORTED' ? 'timeout' : 'network_error',
        {
          errorCode: error.code
        }
      )
      if (diagnosticRecord) {
        pushDiagnosticRecord(diagnosticRecord)
      }
      if (meta.skipErrorMessage) {
        return Promise.reject(error)
      }
      if (!shouldMuteNetworkMessage()) {
        ElMessage.warning(
          error.code === 'ECONNABORTED'
            ? '请求超时，请检查后端服务状态或接口性能'
            : '后端服务未连接，请检查网络或服务状态'
        )
      }
      return Promise.reject(error)
    }

    if (error.response.status >= 500) {
      const diagnosticRecord = buildDiagnosticRecord(diagnosticMeta, 'http_error', {
        statusCode: error.response.status,
        errorCode: error.code
      })
      if (diagnosticRecord) {
        pushDiagnosticRecord(diagnosticRecord)
      }
    }
    if (meta.skipErrorMessage) {
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

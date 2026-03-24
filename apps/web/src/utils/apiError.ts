import type { AxiosError } from 'axios'

interface ApiErrorPayload {
  message?: string
  detail?: string
}

export function resolveApiErrorMessage(error: unknown, fallback: string): string {
  if (!error || typeof error !== 'object') {
    return fallback
  }

  const axiosError = error as AxiosError<ApiErrorPayload>
  if (axiosError.code === 'ECONNABORTED') {
    return '请求超时，请检查后端服务状态或接口性能'
  }

  if (!axiosError.response) {
    return '后端服务未连接，请检查网络或服务状态'
  }

  const payload = axiosError.response.data
  if (typeof payload?.message === 'string' && payload.message.trim()) {
    return payload.message
  }

  if (typeof payload?.detail === 'string' && payload.detail.trim()) {
    return payload.detail
  }

  return fallback
}

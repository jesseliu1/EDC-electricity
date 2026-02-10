import { client } from './client'

export type BaselineStatus = 'draft' | 'published' | 'disabled'

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface BaselineResponse {
  id: string
  name: string
  description: string | null
  source_heat_id: string
  tolerance_percent: number
  status: BaselineStatus
  version: number
  created_at: string
  updated_at: string
  published_at: string | null
  power_curve?: CurvePoint[]
  voltage_curve?: CurvePoint[]
  temperature?: number | null
}

export interface BaselineListResponse {
  items: BaselineResponse[]
  total: number
}

export interface BaselineCreatePayload {
  name: string
  description?: string
  source_heat_id: string
  tolerance_percent: number
}

export interface BaselineUpdatePayload {
  name?: string
  description?: string
  tolerance_percent?: number
}

export const baselineApi = {
  list: (status?: BaselineStatus) =>
    client.get<BaselineListResponse>('/baselines', {
      params: status ? { status } : undefined
    }),
  get: (id: string) => client.get<BaselineResponse>(`/baselines/${id}`),
  create: (payload: BaselineCreatePayload) =>
    client.post<BaselineResponse>('/baselines', payload),
  update: (id: string, payload: BaselineUpdatePayload) =>
    client.patch<BaselineResponse>(`/baselines/${id}`, payload),
  publish: (id: string) => client.post<BaselineResponse>(`/baselines/${id}/publish`),
  disable: (id: string) => client.post<BaselineResponse>(`/baselines/${id}/disable`),
  remove: (id: string) => client.delete(`/baselines/${id}`)
}

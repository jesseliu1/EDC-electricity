import { client } from './client'

export type BaselineStatus = 'draft' | 'published' | 'disabled'

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface CurveData {
  metric_id: string
  metric_name: string
  unit: string
  color: string
  points: CurvePoint[]
}

export interface BaselineResponse {
  id: string
  name: string
  description: string | null
  definition_id: string
  definition_name: string
  source_heat_id: string
  selected_start_time?: string | null
  selected_end_time?: string | null
  tolerance_percent: number
  status: BaselineStatus
  version: number
  created_at: string
  updated_at: string
  published_at: string | null
  curves_data?: CurveData[]
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
  definition_id: string
  source_heat_id: string
  selected_start_time?: string
  selected_end_time?: string
  tolerance_percent: number
}

export interface BaselineUpdatePayload {
  name?: string
  description?: string
  selected_start_time?: string
  selected_end_time?: string
  tolerance_percent?: number
}

export const baselineApi = {
  list: (status?: BaselineStatus, definitionId?: string) =>
    client.get<BaselineListResponse>('/baselines', {
      params: {
        ...(status ? { status } : {}),
        ...(definitionId ? { definition_id: definitionId } : {})
      }
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

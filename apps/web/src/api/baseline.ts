import { client } from './client'

export type BaselineStatus = 'draft' | 'published' | 'disabled'
export type BaselineCurveSource = 'live_edc' | 'demo_curve' | 'none'

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface CurveData {
  metric_id: string
  metric_name: string
  unit: string
  color: string
  edc_channel_id?: string | null
  source_channel_name?: string | null
  source_channel_label?: string | null
  points: CurvePoint[]
}

export interface BaselineResponse {
  id: string
  name: string
  description: string | null
  definition_id: string
  definition_name: string
  expected_duration_minutes: number
  is_default: boolean
  source_heat_id: string | null
  selected_start_time?: number | null
  selected_end_time?: number | null
  effective_from?: number | null
  tolerance_percent: number
  status: BaselineStatus
  version: number
  curve_source: BaselineCurveSource
  created_at: number
  updated_at: number
  published_at: number | null
  curves_data?: CurveData[]
  power_curve?: CurvePoint[]
  voltage_curve?: CurvePoint[]
  temperature?: number | null
}

export interface BaselineListResponse {
  items: BaselineResponse[]
  total: number
}

export interface BaselineSummary {
  id: string
  name: string
  status: BaselineStatus
  version: number
  is_default: boolean
}

export interface BaselineCreatePayload {
  name: string
  description?: string
  definition_id: string
  source_heat_id?: string
  selected_start_time?: number
  selected_end_time?: number
  effective_from?: number
  tolerance_percent: number
  is_default?: boolean
}

export interface BaselineUpdatePayload {
  name?: string
  description?: string
  selected_start_time?: number
  selected_end_time?: number
  effective_from?: number
  tolerance_percent?: number
  is_default?: boolean
}

export const baselineApi = {
  list: (status?: BaselineStatus, definitionId?: string) =>
    client.get<BaselineListResponse>('/baselines', {
      params: {
        ...(status ? { status } : {}),
        ...(definitionId ? { definition_id: definitionId } : {})
      }
    }),
  getActive: () => client.get<BaselineSummary | null>('/baselines/active'),
  get: (id: string) => client.get<BaselineResponse>(`/baselines/${id}`),
  create: (payload: BaselineCreatePayload) =>
    client.post<BaselineResponse>('/baselines', payload),
  update: (id: string, payload: BaselineUpdatePayload) =>
    client.patch<BaselineResponse>(`/baselines/${id}`, payload),
  activate: (id: string) => client.post<BaselineSummary>(`/baselines/${id}/activate`),
  publish: (id: string) => client.post<BaselineResponse>(`/baselines/${id}/publish`),
  disable: (id: string) => client.post<BaselineResponse>(`/baselines/${id}/disable`),
  remove: (id: string) => client.delete(`/baselines/${id}`)
}

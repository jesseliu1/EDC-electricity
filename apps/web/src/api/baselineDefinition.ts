import { client } from './client'

export interface MetricDefinition {
  id: string
  name: string
  unit: string
  color: string
  sort_order: number
  edc_channel_id: string | null
}

export interface BaselineDefinitionResponse {
  id: string
  definition_name: string
  description: string | null
  expected_duration_minutes: number
  status: 'active' | 'disabled'
  metrics: MetricDefinition[]
  instance_count: number
  created_at: string
  updated_at: string
}

export interface BaselineDefinitionListResponse {
  items: BaselineDefinitionResponse[]
  total: number
}

export interface MetricDefinitionCreate {
  name: string
  unit: string
  color: string
  sort_order?: number
  edc_channel_id?: string | null
}

export interface BaselineDefinitionCreatePayload {
  definition_name: string
  description?: string | null
  expected_duration_minutes: number
  metrics?: MetricDefinitionCreate[]
}

export interface BaselineDefinitionUpdatePayload {
  definition_name?: string
  description?: string | null
  expected_duration_minutes?: number
}

export interface MetricDefinitionUpdatePayload {
  name?: string
  unit?: string
  color?: string
  sort_order?: number
  edc_channel_id?: string | null
}

export const baselineDefinitionApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    client.get<BaselineDefinitionListResponse>('/baseline-definitions', { params }),
  get: (id: string) =>
    client.get<BaselineDefinitionResponse>(`/baseline-definitions/${id}`),
  create: (payload: BaselineDefinitionCreatePayload) =>
    client.post<BaselineDefinitionResponse>('/baseline-definitions', payload),
  update: (id: string, payload: BaselineDefinitionUpdatePayload) =>
    client.patch<BaselineDefinitionResponse>(`/baseline-definitions/${id}`, payload),
  remove: (id: string) =>
    client.delete(`/baseline-definitions/${id}`),
  disable: (id: string) =>
    client.post<BaselineDefinitionResponse>(`/baseline-definitions/${id}/disable`),
  enable: (id: string) =>
    client.post<BaselineDefinitionResponse>(`/baseline-definitions/${id}/enable`),
  addMetric: (id: string, metric: MetricDefinitionCreate) =>
    client.post<BaselineDefinitionResponse>(`/baseline-definitions/${id}/metrics`, metric),
  updateMetric: (id: string, metricId: string, payload: MetricDefinitionUpdatePayload) =>
    client.patch<BaselineDefinitionResponse>(
      `/baseline-definitions/${id}/metrics/${metricId}`,
      payload
    ),
  removeMetric: (id: string, metricId: string) =>
    client.delete<BaselineDefinitionResponse>(
      `/baseline-definitions/${id}/metrics/${metricId}`
    )
}

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
  created_at: number
  updated_at: number
}

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface PreviewCurveData {
  metric_id: string
  metric_name: string
  unit: string
  color: string
  edc_channel_id: string | null
  source_channel_name?: string | null
  source_channel_label?: string | null
  points: CurvePoint[]
}

export interface BaselinePreviewResponse {
  definition_id: string
  source_heat_id: string | null
  range_start: number
  range_end: number
  curves_data: PreviewCurveData[]
}

export type BaselinePreviewJobStatus = 'idle' | 'running' | 'succeeded' | 'failed'

export interface BaselinePreviewJobResponse {
  job_key: string
  definition_id: string
  source_heat_id: string | null
  status: BaselinePreviewJobStatus
  range_start: number
  range_end: number
  curves_data: PreviewCurveData[]
  last_error: string | null
  created_at: number | null
  started_at: number | null
  updated_at: number | null
  completed_at: number | null
}

export interface BaselineDefinitionListResponse {
  items: BaselineDefinitionResponse[]
  total: number
}

export interface BaselinePreviewRequestParams {
  heat_id?: string
  range_start?: number
  range_end?: number
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
  getPreviewJob: (id: string, params: BaselinePreviewRequestParams) =>
    client.get<BaselinePreviewJobResponse>(`/baseline-definitions/${id}/preview-jobs`, {
      params
    }),
  startPreviewJob: (id: string, params: BaselinePreviewRequestParams) =>
    client.post<BaselinePreviewJobResponse>(`/baseline-definitions/${id}/preview-jobs`, undefined, {
      params
    }),
  previewCurves: (id: string, params: BaselinePreviewRequestParams) =>
    client.get<BaselinePreviewResponse>(`/baseline-definitions/${id}/preview-curves`, {
      params
    }),
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

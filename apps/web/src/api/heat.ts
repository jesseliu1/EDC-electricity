import { client } from './client'

const HEAT_LIST_TIMEOUT_MS = 45000

export type HeatStatus = 'normal' | 'abnormal' | 'pending'
export type HeatCompletionStatus = 'completed' | 'in_progress'
export type HeatRuntimeSnapshotStatus = 'ready' | 'warming' | 'refreshing_history'
export type HeatDataSource =
  | 'live_edc'
  | 'live_inferred'
  | 'active_runtime'
  | 'demo_seed'
  | 'demo_curve'
  | 'mock_stream'
  | 'mock_curve'
  | 'none'

export interface HeatResponseItem {
  id: string
  heat_no: string
  description: string | null
  start_time: string
  end_time: string
  completion_status: HeatCompletionStatus
  last_point_at: string | null
  baseline_id: string | null
  baseline_version_id: string | null
  baseline_effective_from: string | null
  deviation_percent: number | null
  avg_deviation_percent: number | null
  time_offset_percent: number | null
  mismatch_duration_minutes: number | null
  schedule_tag: 'work' | 'break' | 'off_shift'
  cut_reason: string | null
  cut_status: 'normal' | 'major_issue' | 'blocked'
  major_issue: boolean
  blocked_by_issue: boolean
  status: HeatStatus
  temperature: number | null
  record_source: HeatDataSource
  current_curve_source: HeatDataSource
  baseline_curve_source: HeatDataSource
  created_at: string
}

export interface HeatListResponse {
  items: HeatResponseItem[]
  total: number
  page: number
  page_size: number
  snapshot_status: HeatRuntimeSnapshotStatus
}

export interface HeatListQuery {
  status?: HeatStatus
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface BaselineCurveSimple {
  id: string
  name: string
  power_curve: CurvePoint[]
  voltage_curve: CurvePoint[]
  tolerance_percent: number
}

export interface MetricCompareSeries {
  metric_key: string
  metric_name: string
  unit: string
  color: string
  edc_channel_id?: string | null
  source_channel_name?: string | null
  source_channel_label?: string | null
  baseline_curve: CurvePoint[]
  current_curve: CurvePoint[]
}

export interface DeviationRange {
  start: number
  end: number
  deviation: number
}

export interface HeatWithCurveResponse extends HeatResponseItem {
  power_curve: CurvePoint[]
  voltage_curve: CurvePoint[]
}

export interface HeatCompareResponse {
  heat: HeatWithCurveResponse
  baseline: BaselineCurveSimple | null
  baselines?: BaselineCompareItem[]
  deviation_ranges: DeviationRange[]
  max_deviation: number | null
  avg_deviation: number | null
}

export interface CuttingTimelineEvent {
  timestamp: string
  event_type: string
  title: string
  detail: string
}

export interface CuttingTimelineResponse {
  heat_id: string
  events: CuttingTimelineEvent[]
}

export interface BaselineCompareItem {
  baseline: BaselineCurveSimple
  metric_curves: MetricCompareSeries[]
  deviation_ranges: DeviationRange[]
  max_deviation: number | null
  avg_deviation: number | null
}

export interface HeatUpdatePayload {
  description?: string | null
  start_time?: string
  end_time?: string
  adjust_subsequent?: boolean
}

export interface HeatResumeCuttingPayload {
  adjust_subsequent?: boolean
  note?: string
}

export const heatApi = {
  list: (query: HeatListQuery) =>
    client.get<HeatListResponse>('/heats', {
      params: query,
      timeout: HEAT_LIST_TIMEOUT_MS,
      meta: { operation: 'heat_list' }
    }),
  get: (id: string) => client.get<HeatResponseItem>(`/heats/${id}`),
  getCurve: (id: string) => client.get<HeatWithCurveResponse>(`/heats/${id}/curve`),
  getCompare: (id: string) => client.get<HeatCompareResponse>(`/heats/${id}/compare`),
  getCuttingTimeline: (id: string) =>
    client.get<CuttingTimelineResponse>(`/heats/${id}/cutting-timeline`),
  update: (id: string, payload: HeatUpdatePayload) =>
    client.patch<HeatResponseItem>(`/heats/${id}`, payload),
  resumeCutting: (id: string, payload: HeatResumeCuttingPayload) =>
    client.post<HeatResponseItem>(`/heats/${id}/resume-cutting`, payload)
}

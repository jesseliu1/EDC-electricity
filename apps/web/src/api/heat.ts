import { client } from './client'

export type HeatStatus = 'normal' | 'abnormal' | 'pending'

export interface HeatResponseItem {
  id: string
  heat_no: string
  start_time: string
  end_time: string
  baseline_id: string | null
  deviation_percent: number | null
  avg_deviation_percent: number | null
  status: HeatStatus
  temperature: number | null
  created_at: string
}

export interface HeatListResponse {
  items: HeatResponseItem[]
  total: number
  page: number
  page_size: number
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
  deviation_ranges: DeviationRange[]
  max_deviation: number | null
  avg_deviation: number | null
}

export const heatApi = {
  list: (query: HeatListQuery) => client.get<HeatListResponse>('/heats', { params: query }),
  get: (id: string) => client.get<HeatResponseItem>(`/heats/${id}`),
  getCurve: (id: string) => client.get<HeatWithCurveResponse>(`/heats/${id}/curve`),
  getCompare: (id: string) => client.get<HeatCompareResponse>(`/heats/${id}/compare`)
}

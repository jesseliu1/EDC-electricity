import { client } from './client'

export type TimeRange = '5m' | '1h' | '6h' | '24h'

export interface CurvePoint {
  timestamp: number
  value: number
}

export interface DashboardStatsResponse {
  today_heats: number
  avg_deviation: number
  pending_tasks: number
  active_baseline: string | null
  normal_rate: number
}

export interface RealtimeResponse {
  timestamp: number
  baseline_id?: string | null
  baseline_name?: string | null
  power_source_label?: string | null
  voltage_source_label?: string | null
  power: CurvePoint[]
  voltage: CurvePoint[]
  baseline_power: CurvePoint[]
  baseline_voltage: CurvePoint[]
}

export interface RecentHeatResponseItem {
  id: string
  heat_no: string
  start_time: number
  end_time: number
  status: 'normal' | 'abnormal' | 'pending'
  deviation_percent: number | null
}

export interface RecentHeatsResponse {
  items: RecentHeatResponseItem[]
}

export const dashboardApi = {
  getStats: () => client.get<DashboardStatsResponse>('/dashboard/stats'),
  getRealtime: (duration: TimeRange) =>
    client.get<RealtimeResponse>('/dashboard/realtime', { params: { duration } }),
  getRecentHeats: (limit = 10) =>
    client.get<RecentHeatsResponse>('/dashboard/recent-heats', { params: { limit } })
}

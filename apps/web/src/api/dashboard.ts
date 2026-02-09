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
  timestamp: string
  power: CurvePoint[]
  voltage: CurvePoint[]
  baseline_power: CurvePoint[]
  baseline_voltage: CurvePoint[]
}

export interface RecentHeatResponseItem {
  id: string
  heat_no: string
  start_time: string
  end_time: string
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

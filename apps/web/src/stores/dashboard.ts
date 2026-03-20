import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import type {
  CurvePoint,
  DashboardStatsResponse,
  RecentHeatsResponse,
  RecentHeatResponseItem,
  RealtimeResponse,
  TimeRange
} from '@/api/dashboard'

interface DashboardStats {
  todayHeats: number
  avgDeviation: number
  pendingTasks: number
  activeBaseline: string | null
  normalRate: number
}

interface RealtimeData {
  timestamp: string
  baselineId: string | null
  baselineName: string | null
  powerSourceLabel: string | null
  voltageSourceLabel: string | null
  power: CurvePoint[]
  voltage: CurvePoint[]
  baselinePower: CurvePoint[]
  baselineVoltage: CurvePoint[]
}

export interface RecentHeatItem {
  id: string
  heatNo: string
  startTime: string
  endTime: string
  status: 'normal' | 'abnormal' | 'pending'
  deviationPercent: number | null
}

const defaultStats: DashboardStats = {
  todayHeats: 0,
  avgDeviation: 0,
  pendingTasks: 0,
  activeBaseline: null,
  normalRate: 0
}

const defaultRealtime: RealtimeData = {
  timestamp: '',
  baselineId: null,
  baselineName: null,
  powerSourceLabel: null,
  voltageSourceLabel: null,
  power: [],
  voltage: [],
  baselinePower: [],
  baselineVoltage: []
}

function mapStats(data: DashboardStatsResponse): DashboardStats {
  return {
    todayHeats: data.today_heats,
    avgDeviation: Number(data.avg_deviation.toFixed(1)),
    pendingTasks: data.pending_tasks,
    activeBaseline: data.active_baseline,
    normalRate: Number(data.normal_rate.toFixed(1))
  }
}

function mapRealtime(data: RealtimeResponse): RealtimeData {
  return {
    timestamp: data.timestamp,
    baselineId: data.baseline_id ?? null,
    baselineName: data.baseline_name ?? null,
    powerSourceLabel: data.power_source_label ?? null,
    voltageSourceLabel: data.voltage_source_label ?? null,
    power: data.power,
    voltage: data.voltage,
    baselinePower: data.baseline_power,
    baselineVoltage: data.baseline_voltage
  }
}

function mapRecentHeats(data: RecentHeatsResponse): RecentHeatItem[] {
  return data.items.map((item: RecentHeatResponseItem) => ({
    id: item.id,
    heatNo: item.heat_no,
    startTime: dayjs(item.start_time).format('YYYY-MM-DD HH:mm'),
    endTime: dayjs(item.end_time).format('YYYY-MM-DD HH:mm'),
    status: item.status,
    deviationPercent: item.deviation_percent
  }))
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    stats: { ...defaultStats },
    realtime: { ...defaultRealtime },
    recentHeats: [] as RecentHeatItem[],
    timeRange: '1h' as TimeRange,
    loading: false
  }),
  actions: {
    async fetchStats() {
      try {
        const data = await dashboardApi.getStats()
        this.stats = mapStats(data)
      } catch (error) {
        console.error('Dashboard stats request failed.', error)
        this.stats = { ...defaultStats }
      }
    },
    async fetchRealtime(range?: TimeRange) {
      if (range) this.timeRange = range
      try {
        const data = await dashboardApi.getRealtime(this.timeRange)
        this.realtime = mapRealtime(data)
      } catch (error) {
        console.error('Dashboard realtime request failed.', error)
        this.realtime = { ...defaultRealtime }
      }
    },
    async fetchRecentHeats(limit = 8) {
      try {
        const data = await dashboardApi.getRecentHeats(limit)
        this.recentHeats = mapRecentHeats(data)
      } catch (error) {
        console.error('Dashboard recent heats request failed.', error)
        this.recentHeats = []
      }
    },
    async fetchAll() {
      this.loading = true
      await Promise.all([
        this.fetchStats(),
        this.fetchRealtime(this.timeRange),
        this.fetchRecentHeats()
      ])
      this.loading = false
    }
  }
})

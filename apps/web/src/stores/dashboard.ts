import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import { taskApi } from '@/api/task'
import { resolveApiErrorMessage } from '@/utils/apiError'
import type {
  CurvePoint,
  DashboardStatsResponse,
  RecentHeatsResponse,
  RecentHeatResponseItem,
  RealtimeResponse,
  TimeRange
} from '@/api/dashboard'
import type { TaskItemResponse, TaskStatus } from '@/api/task'

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

export interface DashboardTaskPreviewItem {
  id: string
  taskNo: string
  heatId: string
  deviationPercent: number | null
  status: TaskStatus
  updatedAt: string
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

function mapTaskPreview(item: TaskItemResponse): DashboardTaskPreviewItem {
  return {
    id: item.id,
    taskNo: item.task_no,
    heatId: item.heat_id,
    deviationPercent: item.deviation_percent,
    status: item.status,
    updatedAt: dayjs(item.updated_at).format('YYYY-MM-DD HH:mm')
  }
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    stats: { ...defaultStats },
    statsLoaded: false,
    statsError: null as string | null,
    realtime: { ...defaultRealtime },
    realtimeLoaded: false,
    realtimeError: null as string | null,
    recentHeats: [] as RecentHeatItem[],
    recentHeatsLoaded: false,
    recentHeatsError: null as string | null,
    pendingTaskPreview: [] as DashboardTaskPreviewItem[],
    timeRange: '1h' as TimeRange,
    loading: false
  }),
  actions: {
    async fetchStats() {
      this.statsError = null
      try {
        const data = await dashboardApi.getStats()
        this.stats = mapStats(data)
        this.statsLoaded = true
      } catch (error) {
        console.error('Dashboard stats request failed.', error)
        this.statsError = resolveApiErrorMessage(error, '仪表盘统计加载失败')
      }
    },
    async fetchRealtime(range?: TimeRange) {
      if (range) this.timeRange = range
      this.realtimeError = null
      try {
        const data = await dashboardApi.getRealtime(this.timeRange)
        this.realtime = mapRealtime(data)
        this.realtimeLoaded = true
      } catch (error) {
        console.error('Dashboard realtime request failed.', error)
        this.realtimeError = resolveApiErrorMessage(error, '实时曲线加载失败')
        this.realtimeLoaded = true
      }
    },
    async fetchRecentHeats(limit = 8) {
      this.recentHeatsError = null
      try {
        const data = await dashboardApi.getRecentHeats(limit)
        this.recentHeats = mapRecentHeats(data)
        this.recentHeatsLoaded = true
      } catch (error) {
        console.error('Dashboard recent heats request failed.', error)
        this.recentHeatsError = resolveApiErrorMessage(error, '最近炉次加载失败')
      }
    },
    async fetchPendingTaskPreview(limit = 3) {
      try {
        const [pending, inProgress] = await Promise.all([
          taskApi.list({ status: 'pending', page: 1, page_size: limit }),
          taskApi.list({ status: 'in_progress', page: 1, page_size: limit })
        ])
        const merged = [...pending.items, ...inProgress.items]
          .sort((a, b) => dayjs(b.updated_at).valueOf() - dayjs(a.updated_at).valueOf())
          .slice(0, limit)
        this.pendingTaskPreview = merged.map(mapTaskPreview)
      } catch (error) {
        console.error('Dashboard task preview request failed.', error)
        this.pendingTaskPreview = []
      }
    },
    async fetchAll() {
      this.loading = true
      await Promise.all([
        this.fetchStats(),
        this.fetchRealtime(this.timeRange),
        this.fetchRecentHeats(),
        this.fetchPendingTaskPreview()
      ])
      this.loading = false
    }
  }
})

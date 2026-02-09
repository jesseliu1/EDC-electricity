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
  power: [],
  voltage: [],
  baselinePower: [],
  baselineVoltage: []
}

const rangeMinutes: Record<TimeRange, number> = {
  '5m': 5,
  '1h': 60,
  '6h': 360,
  '24h': 1440
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

function mockStats(): DashboardStats {
  return {
    todayHeats: 12,
    avgDeviation: 3.2,
    pendingTasks: 5,
    activeBaseline: '标准基线 v2.1',
    normalRate: 85
  }
}

function mockRealtime(range: TimeRange): RealtimeData {
  const minutes = rangeMinutes[range]
  const now = dayjs()
  const power: CurvePoint[] = []
  const baselinePower: CurvePoint[] = []
  const voltage: CurvePoint[] = []
  const baselineVoltage: CurvePoint[] = []

  for (let i = 0; i < minutes; i += 1) {
    const timestamp = now.subtract(minutes - i, 'minute').valueOf()
    const basePower = 420 + Math.sin(i / 18) * 30
    const powerValue = basePower + (Math.random() - 0.5) * 12
    const baseVoltage = 380 + Math.sin(i / 25) * 8
    const voltageValue = baseVoltage + (Math.random() - 0.5) * 4

    baselinePower.push({ timestamp, value: Number(basePower.toFixed(1)) })
    power.push({ timestamp, value: Number(powerValue.toFixed(1)) })
    baselineVoltage.push({ timestamp, value: Number(baseVoltage.toFixed(1)) })
    voltage.push({ timestamp, value: Number(voltageValue.toFixed(1)) })
  }

  return {
    timestamp: now.toISOString(),
    power,
    voltage,
    baselinePower,
    baselineVoltage
  }
}

function mockRecentHeats(): RecentHeatItem[] {
  return Array.from({ length: 6 }).map((_, index) => {
    const start = dayjs().subtract(index + 1, 'hour')
    return {
      id: `mock-${index + 1}`,
      heatNo: `H${dayjs().format('YYYYMMDD')}-${String(index + 1).padStart(3, '0')}`,
      startTime: start.format('YYYY-MM-DD HH:mm'),
      endTime: start.add(45, 'minute').format('YYYY-MM-DD HH:mm'),
      status: index % 3 === 0 ? 'abnormal' : index % 4 === 0 ? 'pending' : 'normal',
      deviationPercent: index % 3 === 0 ? Number((10 + index * 1.8).toFixed(1)) : 3.2
    }
  })
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
        console.warn('Dashboard stats fallback to mock.', error)
        this.stats = mockStats()
      }
    },
    async fetchRealtime(range?: TimeRange) {
      if (range) this.timeRange = range
      try {
        const data = await dashboardApi.getRealtime(this.timeRange)
        this.realtime = mapRealtime(data)
      } catch (error) {
        console.warn('Dashboard realtime fallback to mock.', error)
        this.realtime = mockRealtime(this.timeRange)
      }
    },
    async fetchRecentHeats(limit = 8) {
      try {
        const data = await dashboardApi.getRecentHeats(limit)
        this.recentHeats = mapRecentHeats(data)
      } catch (error) {
        console.warn('Dashboard heats fallback to mock.', error)
        this.recentHeats = mockRecentHeats()
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

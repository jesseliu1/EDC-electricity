import { defineStore } from 'pinia'
import { dashboardApi } from '@/api/dashboard'
import { heatApi } from '@/api/heat'
import { taskApi } from '@/api/task'
import { resolveApiErrorMessage } from '@/utils/apiError'
import type {
  DashboardStatsResponse,
  RecentHeatsResponse,
  RecentHeatResponseItem,
  RealtimeResponse,
  TimeRange
} from '@/api/dashboard'
import type { TaskItemResponse, TaskStatus } from '@/api/task'
import type {
  BaselineCompareItem,
  CurvePoint,
  DeviationRange,
  HeatCompareResponse,
  MetricCompareSeries,
} from '@/api/heat'

interface DashboardStats {
  todayHeats: number
  avgDeviationScore: number
  pendingTasks: number
  activeBaseline: string | null
  normalRate: number
}

interface RealtimeData {
  timestamp: number | null
  baselineId: string | null
  baselineName: string | null
  powerSourceLabel: string | null
  voltageSourceLabel: string | null
  power: CurvePoint[]
  voltage: CurvePoint[]
  baselinePower: CurvePoint[]
  baselineVoltage: CurvePoint[]
}

interface TimeWindow {
  start: number
  end: number
}

type DashboardCurrentHeatEmptyReason = 'no_current_heat' | 'no_compare_baseline' | null

interface DashboardCurrentHeatCompare {
  currentHeatId: string | null
  currentHeatNo: string | null
  currentHeatStartTime: number | null
  baselineName: string | null
  activeBaselineId: string | null
  baselineComparisons: BaselineCompareItem[]
  heatCoreWindow: TimeWindow | null
  compareContextWindow: TimeWindow | null
  fallbackDeviationRanges: DeviationRange[]
}

export interface RecentHeatItem {
  id: string
  heatNo: string
  startTime: number
  endTime: number
  status: 'normal' | 'abnormal' | 'pending'
  deviationScore: number | null
}

export interface DashboardTaskPreviewItem {
  id: string
  taskNo: string
  heatId: string
  deviationScore: number | null
  status: TaskStatus
  updatedAt: number
}

const defaultStats: DashboardStats = {
  todayHeats: 0,
  avgDeviationScore: 0,
  pendingTasks: 0,
  activeBaseline: null,
  normalRate: 0
}

const defaultRealtime: RealtimeData = {
  timestamp: null,
  baselineId: null,
  baselineName: null,
  powerSourceLabel: null,
  voltageSourceLabel: null,
  power: [],
  voltage: [],
  baselinePower: [],
  baselineVoltage: []
}

const defaultCurrentHeatCompare: DashboardCurrentHeatCompare = {
  currentHeatId: null,
  currentHeatNo: null,
  currentHeatStartTime: null,
  baselineName: null,
  activeBaselineId: null,
  baselineComparisons: [],
  heatCoreWindow: null,
  compareContextWindow: null,
  fallbackDeviationRanges: [],
}

function mapStats(data: DashboardStatsResponse): DashboardStats {
  return {
    todayHeats: data.today_heats,
    avgDeviationScore: Number(data.avg_deviation_score.toFixed(1)),
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

function normalizedTimestamp(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return null
  const timestamp = Number(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function inferCurveWindow(curves: Array<Array<{ timestamp: number; value: number }>>) {
  const timestamps = curves.flatMap((curve) => curve.map((point) => point.timestamp))
  if (timestamps.length === 0) return null

  return {
    start: Math.min(...timestamps),
    end: Math.max(...timestamps),
  }
}

function selectPrimaryComparison(compare: HeatCompareResponse) {
  const comparisons = compare.baselines || []
  if (comparisons.length === 0) return null

  return (
    comparisons.find((item) => item.baseline.id === compare.heat.baseline_id) ||
    (compare.baseline ? comparisons.find((item) => item.baseline.id === compare.baseline?.id) : null) ||
    comparisons[0] ||
    null
  )
}

function buildHeatCoreWindow(compare: HeatCompareResponse) {
  const heatEnd =
    compare.heat.completion_status === 'in_progress'
      ? compare.heat.last_point_at || compare.heat.end_time
      : compare.heat.end_time
  return {
    start: compare.heat.start_time,
    end: heatEnd,
  }
}

function buildCompareContextWindow(
  compare: HeatCompareResponse,
  metricCurves: MetricCompareSeries[],
  heatCoreWindow: TimeWindow
) {
  const explicitActualStart = normalizedTimestamp(compare.heat.actual_context_start_time)
  const explicitActualEnd = normalizedTimestamp(compare.heat.actual_context_end_time)
  if (
    explicitActualStart !== null &&
    explicitActualEnd !== null &&
    explicitActualStart <= explicitActualEnd
  ) {
    return {
      start: explicitActualStart,
      end: explicitActualEnd,
    }
  }

  const explicitDeclaredStart = normalizedTimestamp(compare.heat.context_start_time)
  const explicitDeclaredEnd = normalizedTimestamp(compare.heat.context_end_time)
  if (
    explicitDeclaredStart !== null &&
    explicitDeclaredEnd !== null &&
    explicitDeclaredStart <= explicitDeclaredEnd
  ) {
    return {
      start: Math.min(explicitDeclaredStart, heatCoreWindow.start),
      end: Math.max(explicitDeclaredEnd, heatCoreWindow.end),
    }
  }

  return inferCurveWindow(metricCurves.map((metric) => metric.current_curve)) || heatCoreWindow
}

function mapCurrentHeatCompare(compare: HeatCompareResponse): DashboardCurrentHeatCompare | null {
  const primaryComparison = selectPrimaryComparison(compare)
  if (!primaryComparison || primaryComparison.metric_curves.length === 0) {
    return null
  }

  const heatCoreWindow = buildHeatCoreWindow(compare)
  return {
    currentHeatId: compare.heat.id,
    currentHeatNo: compare.heat.heat_no,
    currentHeatStartTime: compare.heat.start_time,
    baselineName: primaryComparison.baseline.name,
    activeBaselineId: primaryComparison.baseline.id,
    baselineComparisons: [primaryComparison],
    heatCoreWindow,
    compareContextWindow: buildCompareContextWindow(
      compare,
      primaryComparison.metric_curves,
      heatCoreWindow
    ),
    fallbackDeviationRanges: primaryComparison.deviation_ranges || compare.deviation_ranges,
  }
}

function mapRecentHeats(data: RecentHeatsResponse): RecentHeatItem[] {
  return data.items.map((item: RecentHeatResponseItem) => ({
    id: item.id,
    heatNo: item.heat_no,
    startTime: item.start_time,
    endTime: item.end_time,
    status: item.status,
    deviationScore: item.deviation_score
  }))
}

function mapTaskPreview(item: TaskItemResponse): DashboardTaskPreviewItem {
  return {
    id: item.id,
    taskNo: item.task_no,
    heatId: item.heat_id,
    deviationScore: item.deviation_score,
    status: item.status,
    updatedAt: item.updated_at
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
    currentHeatCompare: { ...defaultCurrentHeatCompare },
    currentHeatCompareLoaded: false,
    currentHeatCompareError: null as string | null,
    currentHeatCompareEmptyReason: null as DashboardCurrentHeatEmptyReason,
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
    async fetchCurrentHeatCompare() {
      this.currentHeatCompareLoaded = false
      this.currentHeatCompareError = null
      this.currentHeatCompareEmptyReason = null
      this.currentHeatCompare = { ...defaultCurrentHeatCompare }
      try {
        const heatList = await heatApi.list({ page: 1, page_size: 20 })
        const currentHeat = heatList.items.find((item) => item.realtime_current)
        if (!currentHeat) {
          this.currentHeatCompareLoaded = true
          this.currentHeatCompareEmptyReason = 'no_current_heat'
          return
        }

        const compare = await heatApi.getCompare(currentHeat.id)
        const mapped = mapCurrentHeatCompare(compare)
        if (!mapped) {
          this.currentHeatCompareLoaded = true
          this.currentHeatCompareEmptyReason = 'no_compare_baseline'
          return
        }

        this.currentHeatCompare = mapped
        this.currentHeatCompareLoaded = true
      } catch (error) {
        console.error('Dashboard current heat compare request failed.', error)
        this.currentHeatCompareError = resolveApiErrorMessage(error, '当前炉次对比加载失败')
        this.currentHeatCompareLoaded = true
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
          .sort((a, b) => b.updated_at - a.updated_at)
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
        this.fetchCurrentHeatCompare(),
        this.fetchRecentHeats(),
        this.fetchPendingTaskPreview()
      ])
      this.loading = false
    }
  }
})

import { defineStore } from 'pinia'
import { heatApi } from '@/api/heat'
import { resolveApiErrorMessage } from '@/utils/apiError'
import {
  plantDateRangeFromPicker,
  timestampToDate,
  toTimestampMs,
} from '@/utils/time'
import type {
  BaselineCompareItem,
  CuttingTimelineEvent,
  CurvePoint,
  DeviationRange,
  HeatCompletionStatus,
  HeatDataSource,
  HeatCompareResponse,
  HeatListQuery,
  HeatRuntimeSnapshotStatus,
  HeatResponseItem,
  HeatStatus,
} from '@/api/heat'

export interface HeatItem {
  id: string
  heatNo: string
  description: string | null
  startTime: number
  endTime: number
  contextStartTime: number | null
  contextEndTime: number | null
  completionStatus: HeatCompletionStatus
  lastPointAt: number | null
  runtimeSnapshotStatus: HeatRuntimeSnapshotStatus
  realtimeCurrent: boolean
  baselineId: string | null
  baselineVersionId: string | null
  baselineEffectiveFrom: number | null
  deviationScore: number | null
  avgDeviationScore: number | null
  abnormalDurationMinutes: number | null
  scheduleTag: 'work' | 'break' | 'off_shift'
  cutReason: string | null
  cutStatus: 'normal' | 'major_issue' | 'blocked'
  majorIssue: boolean
  blockedByIssue: boolean
  status: HeatStatus
  temperature: number | null
  recordSource: HeatDataSource
  currentCurveSource: HeatDataSource
  baselineCurveSource: HeatDataSource
}

interface HeatFilters {
  status: 'all' | HeatStatus
  dateRange: [Date, Date] | null
}

const HEAT_VIEW_STATE_KEY = 'edc-heat-view-state'

function readHeatViewState(): {
  page: number
  pageSize: number
  filters: HeatFilters
} {
  if (typeof window === 'undefined') {
    return {
      page: 1,
      pageSize: 10,
      filters: { status: 'all', dateRange: null }
    }
  }

  try {
    const raw = window.localStorage.getItem(HEAT_VIEW_STATE_KEY)
    if (!raw) {
      throw new Error('missing')
    }

    const parsed = JSON.parse(raw) as {
      page?: number
      pageSize?: number
      status?: HeatFilters['status']
      dateRange?: [number | string, number | string] | null
    }
    const start = toTimestampMs(parsed.dateRange?.[0])
    const end = toTimestampMs(parsed.dateRange?.[1])

    return {
      page: parsed.page && parsed.page > 0 ? parsed.page : 1,
      pageSize: parsed.pageSize && parsed.pageSize > 0 ? parsed.pageSize : 10,
      filters: {
        status: parsed.status || 'all',
        dateRange: start !== null && end !== null ? [timestampToDate(start)!, timestampToDate(end)!] : null
      }
    }
  } catch {
    return {
      page: 1,
      pageSize: 10,
      filters: { status: 'all', dateRange: null }
    }
  }
}

export interface HeatDetail {
  base: HeatItem
  powerCurve: CurvePoint[]
  voltageCurve: CurvePoint[]
  baselineName: string | null
  baselinePowerCurve: CurvePoint[]
  baselineComparisons: BaselineCompareItem[]
  deviationRanges: DeviationRange[]
  deviationScore: number | null
  avgDeviationScore: number | null
  cuttingTimeline: CuttingTimelineEvent[]
}

export interface HeatPreview {
  powerCurve: CurvePoint[]
  voltageCurve: CurvePoint[]
  temperatureCurve: CurvePoint[]
}

function persistHeatViewState(state: {
  page: number
  pageSize: number
  filters: HeatFilters
}) {
  if (typeof window === 'undefined') return

  const payload = {
    page: state.page,
    pageSize: state.pageSize,
    status: state.filters.status,
    dateRange: state.filters.dateRange
      ? [toTimestampMs(state.filters.dateRange[0]), toTimestampMs(state.filters.dateRange[1])]
      : null
  }
  window.localStorage.setItem(HEAT_VIEW_STATE_KEY, JSON.stringify(payload))
}

function mapHeat(item: HeatResponseItem): HeatItem {
  return {
    id: item.id,
    heatNo: item.heat_no,
    description: item.description ?? null,
    startTime: item.start_time,
    endTime: item.end_time,
    contextStartTime: item.context_start_time ?? null,
    contextEndTime: item.context_end_time ?? null,
    completionStatus: item.completion_status || 'completed',
    lastPointAt: item.last_point_at,
    runtimeSnapshotStatus: item.runtime_snapshot_status || 'warming',
    realtimeCurrent: Boolean(item.realtime_current),
    baselineId: item.baseline_id,
    baselineVersionId: item.baseline_version_id,
    baselineEffectiveFrom: item.baseline_effective_from,
    deviationScore: item.deviation_score,
    avgDeviationScore: item.avg_deviation_score,
    abnormalDurationMinutes: item.abnormal_duration_minutes,
    scheduleTag: item.schedule_tag,
    cutReason: item.cut_reason,
    cutStatus: item.cut_status,
    majorIssue: item.major_issue,
    blockedByIssue: item.blocked_by_issue,
    status: item.status,
    temperature: item.temperature,
    recordSource: item.record_source,
    currentCurveSource: item.current_curve_source,
    baselineCurveSource: item.baseline_curve_source
  }
}

function mapDetail(
  compare: HeatCompareResponse,
  timeline: CuttingTimelineEvent[]
): HeatDetail {
  const comparisons: BaselineCompareItem[] = compare.baselines ||
    (compare.baseline
      ? [
          {
            baseline: compare.baseline,
            metric_curves: [],
            deviation_ranges: compare.deviation_ranges,
            deviation_score: compare.deviation_score,
            avg_deviation_score: compare.avg_deviation_score
          }
        ]
      : [])

  return {
    base: mapHeat(compare.heat),
    powerCurve: compare.heat.power_curve,
    voltageCurve: compare.heat.voltage_curve,
    baselineName: comparisons[0]?.baseline.name || null,
    baselinePowerCurve: comparisons[0]?.baseline.power_curve || [],
    baselineComparisons: comparisons,
    deviationRanges: comparisons[0]?.deviation_ranges || [],
    deviationScore: comparisons[0]?.deviation_score || null,
    avgDeviationScore: comparisons[0]?.avg_deviation_score || null,
    cuttingTimeline: timeline
  }
}

export const useHeatStore = defineStore('heat', {
  state: () => {
    const persisted = readHeatViewState()
    return {
      list: [] as HeatItem[],
      current: null as HeatDetail | null,
      previews: {} as Record<string, HeatPreview>,
      loading: false,
      detailLoading: false,
      detailError: null as string | null,
      refreshError: null as string | null,
      page: persisted.page,
      pageSize: persisted.pageSize,
      total: 0,
      snapshotStatus: 'warming' as HeatRuntimeSnapshotStatus,
      snapshotWatermark: null as number | null,
      lastRefreshStartedAt: null as number | null,
      lastRefreshCompletedAt: null as number | null,
      refreshFailureCount: 0,
      refreshFailureMessage: null as string | null,
      filters: persisted.filters
    }
  },
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const plantRange = plantDateRangeFromPicker(this.filters.dateRange)
        const query: HeatListQuery = {
          page: this.page,
          page_size: this.pageSize,
          status: this.filters.status === 'all' ? undefined : this.filters.status,
          start_date: plantRange?.start,
          end_date: plantRange?.end,
        }
        const data = await heatApi.list(query)
        this.list = data.items.map(mapHeat)
        this.total = data.total
        this.snapshotStatus = data.snapshot_status
        this.snapshotWatermark = data.snapshot_watermark
        this.lastRefreshStartedAt = data.last_refresh_started_at
        this.lastRefreshCompletedAt = data.last_refresh_completed_at
        this.refreshFailureCount = data.refresh_failure_count || 0
        this.refreshFailureMessage = data.refresh_error || null
        persistHeatViewState({
          page: this.page,
          pageSize: this.pageSize,
          filters: this.filters
        })
      } catch (error) {
        console.error('Heat list request failed.', error)
        this.list = []
        this.total = 0
        this.snapshotStatus = 'warming'
        this.snapshotWatermark = null
        this.lastRefreshStartedAt = null
        this.lastRefreshCompletedAt = null
        this.refreshFailureCount = 0
        this.refreshFailureMessage = resolveApiErrorMessage(error, '炉次列表加载失败')
      } finally {
        this.loading = false
      }
    },
    async setStatus(status: 'all' | HeatStatus) {
      this.filters.status = status
      this.page = 1
      persistHeatViewState({
        page: this.page,
        pageSize: this.pageSize,
        filters: this.filters
      })
      await this.fetchList()
    },
    async setDateRange(dateRange: [Date, Date] | null) {
      this.filters.dateRange = dateRange
      this.page = 1
      persistHeatViewState({
        page: this.page,
        pageSize: this.pageSize,
        filters: this.filters
      })
      await this.fetchList()
    },
    async resetFilters() {
      this.filters.status = 'all'
      this.filters.dateRange = null
      this.page = 1
      persistHeatViewState({
        page: this.page,
        pageSize: this.pageSize,
        filters: this.filters
      })
      await this.fetchList()
    },
    async setPage(page: number) {
      this.page = page
      persistHeatViewState({
        page: this.page,
        pageSize: this.pageSize,
        filters: this.filters
      })
      await this.fetchList()
    },
    async setPageSize(pageSize: number) {
      this.pageSize = pageSize
      this.page = 1
      persistHeatViewState({
        page: this.page,
        pageSize: this.pageSize,
        filters: this.filters
      })
      await this.fetchList()
    },
    async fetchDetail(id: string) {
      this.detailLoading = true
      this.detailError = null
      this.refreshError = null
      this.current = null
      try {
        const [compare, timeline] = await Promise.all([
          heatApi.getCompare(id),
          heatApi.getCuttingTimeline(id)
        ])
        this.current = mapDetail(compare, timeline.events)
      } catch (error) {
        console.error('Heat detail request failed.', error)
        this.current = null
        this.detailError = resolveApiErrorMessage(error, '炉次详情加载失败')
      } finally {
        this.detailLoading = false
      }
    },
    async refreshDetail(id: string) {
      if (!id) return

      try {
        const [compare, timeline] = await Promise.all([
          heatApi.getCompare(id),
          heatApi.getCuttingTimeline(id)
        ])
        this.current = mapDetail(compare, timeline.events)
        this.refreshError = null
      } catch (error) {
        console.error('Heat detail refresh failed.', error)
        this.refreshError = resolveApiErrorMessage(error, '炉次数据刷新失败')
      }
    },
    async fetchPreview(id: string) {
      if (this.previews[id]) {
        return
      }

      try {
        const compare = await heatApi.getCompare(id)
        const temperatureCurve =
          compare.baselines?.[0]?.metric_curves.find(item => item.metric_key === 'temperature')
            ?.current_curve || []

        this.previews[id] = {
          powerCurve: compare.heat.power_curve,
          voltageCurve: compare.heat.voltage_curve,
          temperatureCurve
        }
      } catch (error) {
        console.error('Heat preview request failed.', error)
        this.previews[id] = {
          powerCurve: [],
          voltageCurve: [],
          temperatureCurve: []
        }
      }
    },
    async updateDescription(id: string, description: string) {
      try {
        await heatApi.update(id, { description })
        if (this.current && this.current.base.id === id) {
          this.current.base.description = description
        }
        const item = this.list.find(h => h.id === id)
        if (item) item.description = description
      } catch (error) {
        console.warn('Update heat description failed.', error)
      }
    },
    async updateTiming(id: string, startTime: number, endTime: number, adjustSubsequent: boolean) {
      try {
        const updated = await heatApi.update(id, {
          start_time: startTime,
          end_time: endTime,
          adjust_subsequent: adjustSubsequent
        })
        const mapped = mapHeat(updated)
        if (this.current && this.current.base.id === id) {
          this.current.base.startTime = mapped.startTime
          this.current.base.endTime = mapped.endTime
        }
        const item = this.list.find(h => h.id === id)
        if (item) {
          item.startTime = mapped.startTime
          item.endTime = mapped.endTime
        }
      } catch (error) {
        console.warn('Update heat timing failed.', error)
      }
    },
    async resumeCutting(id: string, adjustSubsequent: boolean) {
      try {
        const updated = await heatApi.resumeCutting(id, { adjust_subsequent: adjustSubsequent })
        const mapped = mapHeat(updated)

        if (this.current && this.current.base.id === id) {
          this.current.base = {
            ...this.current.base,
            ...mapped
          }
        }

        const item = this.list.find(h => h.id === id)
        if (item) {
          Object.assign(item, mapped)
        }

        if (adjustSubsequent) {
          await this.fetchList()
        }
      } catch (error) {
        console.warn('Resume cutting failed.', error)
      }
    }
  }
})

import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { heatApi } from '@/api/heat'
import type {
  BaselineCompareItem,
  CuttingTimelineEvent,
  CurvePoint,
  DeviationRange,
  HeatCompareResponse,
  HeatListQuery,
  MetricCompareSeries,
  HeatResponseItem,
  HeatStatus,
  HeatWithCurveResponse
} from '@/api/heat'

export interface HeatItem {
  id: string
  heatNo: string
  description: string | null
  startTime: string
  endTime: string
  baselineId: string | null
  deviationPercent: number | null
  avgDeviationPercent: number | null
  timeOffsetPercent: number | null
  mismatchDurationMinutes: number | null
  scheduleTag: 'work' | 'break' | 'off_shift'
  cutReason: string | null
  cutStatus: 'normal' | 'major_issue' | 'blocked'
  majorIssue: boolean
  blockedByIssue: boolean
  status: HeatStatus
  temperature: number | null
}

interface HeatFilters {
  status: 'all' | HeatStatus
  dateRange: [Date, Date] | null
}

export interface HeatDetail {
  base: HeatItem
  powerCurve: CurvePoint[]
  voltageCurve: CurvePoint[]
  baselineName: string | null
  baselinePowerCurve: CurvePoint[]
  baselineComparisons: BaselineCompareItem[]
  deviationRanges: DeviationRange[]
  maxDeviation: number | null
  avgDeviation: number | null
  cuttingTimeline: CuttingTimelineEvent[]
}

function mapHeat(item: HeatResponseItem): HeatItem {
  return {
    id: item.id,
    heatNo: item.heat_no,
    description: item.description ?? null,
    startTime: dayjs(item.start_time).format('YYYY-MM-DD HH:mm'),
    endTime: dayjs(item.end_time).format('YYYY-MM-DD HH:mm'),
    baselineId: item.baseline_id,
    deviationPercent: item.deviation_percent,
    avgDeviationPercent: item.avg_deviation_percent,
    timeOffsetPercent: item.time_offset_percent,
    mismatchDurationMinutes: item.mismatch_duration_minutes,
    scheduleTag: item.schedule_tag,
    cutReason: item.cut_reason,
    cutStatus: item.cut_status,
    majorIssue: item.major_issue,
    blockedByIssue: item.blocked_by_issue,
    status: item.status,
    temperature: item.temperature
  }
}

function mockHeats(page: number, pageSize: number, status: 'all' | HeatStatus): { items: HeatItem[]; total: number } {
  const total = 42
  const all = Array.from({ length: total }).map((_, idx) => {
    const now = dayjs().subtract(idx + 1, 'hour')
    const currentStatus: HeatStatus = idx % 5 === 0 ? 'abnormal' : idx % 7 === 0 ? 'pending' : 'normal'
    const cutStatus: HeatItem['cutStatus'] = currentStatus === 'pending' ? 'blocked' : 'normal'
    const scheduleTag: HeatItem['scheduleTag'] = currentStatus === 'pending' ? 'off_shift' : 'work'
    return {
      id: `mock-heat-${idx + 1}`,
      heatNo: `H${dayjs().format('YYYYMMDD')}-${String(idx + 1).padStart(3, '0')}`,
      description: null,
      startTime: now.format('YYYY-MM-DD HH:mm'),
      endTime: now.add(45, 'minute').format('YYYY-MM-DD HH:mm'),
      baselineId: idx % 2 === 0 ? 'baseline-001' : null,
      deviationPercent: currentStatus === 'pending' ? null : Number((3 + (idx % 8) * 1.7).toFixed(1)),
      avgDeviationPercent: currentStatus === 'pending' ? null : Number((2 + (idx % 6) * 1.2).toFixed(1)),
      timeOffsetPercent: currentStatus === 'pending' ? null : Number((idx % 5) * 1.6),
      mismatchDurationMinutes: currentStatus === 'pending' ? null : 3 + (idx % 6),
      scheduleTag,
      cutReason: currentStatus === 'pending' ? 'schedule_window' : 'within_tolerance',
      cutStatus,
      majorIssue: false,
      blockedByIssue: currentStatus === 'pending',
      status: currentStatus,
      temperature: 1450 + (idx % 5) * 6
    }
  })

  const filtered = status === 'all' ? all : all.filter(item => item.status === status)
  const start = (page - 1) * pageSize
  const end = start + pageSize
  return {
    items: filtered.slice(start, end),
    total: filtered.length
  }
}

function mockDetail(id: string): HeatDetail {
  const start = dayjs().subtract(1, 'hour')
  const base: HeatItem = {
    id,
    heatNo: `H${dayjs().format('YYYYMMDD')}-001`,
    description: null,
    startTime: start.format('YYYY-MM-DD HH:mm'),
    endTime: start.add(45, 'minute').format('YYYY-MM-DD HH:mm'),
    baselineId: 'baseline-001',
    deviationPercent: 12.5,
    avgDeviationPercent: 6.8,
    timeOffsetPercent: 5.2,
    mismatchDurationMinutes: 11,
    scheduleTag: 'work',
    cutReason: 'continuous_mismatch',
    cutStatus: 'major_issue',
    majorIssue: true,
    blockedByIssue: false,
    status: 'abnormal',
    temperature: 1458
  }

  const powerCurve = Array.from({ length: 60 }).map((_, i) => ({
    timestamp: start.add(i, 'minute').valueOf(),
    value: Number((430 + Math.sin(i / 8) * 30 + (Math.random() - 0.5) * 8).toFixed(1))
  }))
  const baselinePowerCurve = Array.from({ length: 60 }).map((_, i) => ({
    timestamp: start.add(i, 'minute').valueOf(),
    value: Number((438 + Math.sin(i / 8) * 22).toFixed(1))
  }))
  const voltageCurve = Array.from({ length: 60 }).map((_, i) => ({
    timestamp: start.add(i, 'minute').valueOf(),
    value: Number((380 + Math.cos(i / 9) * 7).toFixed(1))
  }))
  const temperatureCurve = Array.from({ length: 60 }).map((_, i) => ({
    timestamp: start.add(i, 'minute').valueOf(),
    value: Number((1460 + Math.sin(i / 10) * 18).toFixed(1))
  }))
  const pressureCurve = Array.from({ length: 60 }).map((_, i) => ({
    timestamp: start.add(i, 'minute').valueOf(),
    value: Number((0.82 + Math.cos(i / 8) * 0.08).toFixed(2))
  }))

  const buildMetricCurves = (baselineId: string): MetricCompareSeries[] => {
    const baselineIndex = baselineId === 'baseline-001' ? 0 : 1
    const metricCurves: MetricCompareSeries[] = [
      {
        metric_key: 'power',
        metric_name: '功率',
        unit: 'kW',
        color: '#409EFF',
        edc_channel_id: '2349-199',
        source_channel_name: '总有功功率',
        source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / 总有功功率 / kW',
        baseline_curve: baselinePowerCurve.map(item => ({ ...item, value: Number((item.value + baselineIndex * 8).toFixed(1)) })),
        current_curve: powerCurve
      },
      {
        metric_key: 'voltage',
        metric_name: '电压',
        unit: 'V',
        color: '#67C23A',
        edc_channel_id: '2349-128',
        source_channel_name: 'A相电压',
        source_channel_label: 'SSTW 380V-220V電力 · 三相智能电表 / A相电压 / V',
        baseline_curve: voltageCurve.map(item => ({ ...item, value: Number((item.value + baselineIndex * 2).toFixed(1)) })),
        current_curve: voltageCurve
      },
      {
        metric_key: 'temperature',
        metric_name: '炉温',
        unit: '°C',
        color: '#E6A23C',
        edc_channel_id: '2054-128',
        source_channel_name: '热电偶温度采集通道',
        source_channel_label: 'A-1溫度 · 热电偶温度采集器 / 热电偶温度采集通道 / ℃',
        baseline_curve: temperatureCurve.map(item => ({ ...item, value: Number((item.value + 6 + baselineIndex * 12).toFixed(1)) })),
        current_curve: temperatureCurve
      }
    ]

    if (baselineId === 'baseline-002') {
      metricCurves.push({
        metric_key: 'pressure',
        metric_name: '炉压',
        unit: 'MPa',
        color: '#F56C6C',
        edc_channel_id: '769-128',
        source_channel_name: 'AD_CH1',
        source_channel_label: '防水型智慧電流信號轉換器 · AD_CH1 / 外部传感器决定',
        baseline_curve: pressureCurve.map(item => ({ ...item, value: Number((item.value + 0.04).toFixed(2)) })),
        current_curve: pressureCurve
      })
    }

    return metricCurves
  }

  const safeRange = (startIndex: number, endIndex: number, deviation: number): DeviationRange => {
    const startPoint = powerCurve[startIndex]
    const endPoint = powerCurve[endIndex]
    const fallback = powerCurve[0]
    return {
      start: startPoint?.timestamp ?? fallback?.timestamp ?? Date.now(),
      end: endPoint?.timestamp ?? fallback?.timestamp ?? Date.now(),
      deviation
    }
  }

  return {
    base,
    powerCurve,
    voltageCurve,
    baselineName: '标准基线 v2.1',
    baselinePowerCurve,
    baselineComparisons: [
      {
        baseline: {
          id: 'baseline-001',
          name: '标准基线 v2.1',
          power_curve: baselinePowerCurve,
          voltage_curve: voltageCurve,
          tolerance_percent: 15
        },
        metric_curves: buildMetricCurves('baseline-001'),
        deviation_ranges: [
          safeRange(18, 25, 16.4)
        ],
        max_deviation: 21.2,
        avg_deviation: 6.8
      },
      {
        baseline: {
          id: 'baseline-002',
          name: '高功率基线',
          power_curve: baselinePowerCurve.map(item => ({ ...item, value: item.value + 8 })),
          voltage_curve: voltageCurve,
          tolerance_percent: 15
        },
        metric_curves: buildMetricCurves('baseline-002'),
        deviation_ranges: [
          safeRange(32, 40, 14.2)
        ],
        max_deviation: 19.1,
        avg_deviation: 5.9
      }
    ],
    deviationRanges: [
      safeRange(18, 25, 16.4),
      safeRange(38, 45, 21.2)
    ],
    maxDeviation: 21.2,
    avgDeviation: 6.8,
    cuttingTimeline: [
      {
        timestamp: dayjs(base.startTime).toISOString(),
        event_type: 'stream_in',
        title: '实时流入',
        detail: '炉次进入判定队列'
      },
      {
        timestamp: dayjs(base.startTime).add(1, 'minute').toISOString(),
        event_type: 'window_check',
        title: '窗口判定',
        detail: '连续不一致 11 分钟，阈值 8 分钟'
      },
      {
        timestamp: dayjs(base.startTime).add(3, 'minute').toISOString(),
        event_type: 'major_issue',
        title: '触发重大事故',
        detail: '后续炉次阻断'
      }
    ]
  }
}

function mapDetail(
  base: HeatResponseItem,
  curve: HeatWithCurveResponse,
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
            max_deviation: compare.max_deviation,
            avg_deviation: compare.avg_deviation
          }
        ]
      : [])

  return {
    base: mapHeat(base),
    powerCurve: curve.power_curve,
    voltageCurve: curve.voltage_curve,
    baselineName: comparisons[0]?.baseline.name || null,
    baselinePowerCurve: comparisons[0]?.baseline.power_curve || [],
    baselineComparisons: comparisons,
    deviationRanges: comparisons[0]?.deviation_ranges || [],
    maxDeviation: comparisons[0]?.max_deviation || null,
    avgDeviation: comparisons[0]?.avg_deviation || null,
    cuttingTimeline: timeline
  }
}

export const useHeatStore = defineStore('heat', {
  state: () => ({
    list: [] as HeatItem[],
    current: null as HeatDetail | null,
    loading: false,
    page: 1,
    pageSize: 10,
    total: 0,
    filters: {
      status: 'all',
      dateRange: null
    } as HeatFilters
  }),
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const query: HeatListQuery = {
          page: this.page,
          page_size: this.pageSize,
          status: this.filters.status === 'all' ? undefined : this.filters.status,
          start_date: this.filters.dateRange?.[0]
            ? dayjs(this.filters.dateRange[0]).toISOString()
            : undefined,
          end_date: this.filters.dateRange?.[1]
            ? dayjs(this.filters.dateRange[1]).toISOString()
            : undefined
        }
        const data = await heatApi.list(query)
        this.list = data.items.map(mapHeat)
        this.total = data.total
      } catch (error) {
        console.warn('Heat list fallback to mock.', error)
        const mock = mockHeats(this.page, this.pageSize, this.filters.status)
        this.list = mock.items
        this.total = mock.total
      } finally {
        this.loading = false
      }
    },
    async ingestMockHeat() {
      try {
        await heatApi.ingestMock()
        await this.fetchList()
      } catch (error) {
        console.warn('Ingest mock heat failed.', error)
      }
    },
    async setStatus(status: 'all' | HeatStatus) {
      this.filters.status = status
      this.page = 1
      await this.fetchList()
    },
    async setDateRange(dateRange: [Date, Date] | null) {
      this.filters.dateRange = dateRange
      this.page = 1
      await this.fetchList()
    },
    async setPage(page: number) {
      this.page = page
      await this.fetchList()
    },
    async setPageSize(pageSize: number) {
      this.pageSize = pageSize
      this.page = 1
      await this.fetchList()
    },
    async fetchDetail(id: string) {
      this.loading = true
      try {
        const [base, curve, compare, timeline] = await Promise.all([
          heatApi.get(id),
          heatApi.getCurve(id),
          heatApi.getCompare(id),
          heatApi.getCuttingTimeline(id)
        ])
        this.current = mapDetail(base, curve, compare, timeline.events)
      } catch (error) {
        console.warn('Heat detail fallback to mock.', error)
        this.current = mockDetail(id)
      } finally {
        this.loading = false
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
    async updateTiming(id: string, startTime: string, endTime: string, adjustSubsequent: boolean) {
      try {
        const updated = await heatApi.update(id, {
          start_time: dayjs(startTime).toISOString(),
          end_time: dayjs(endTime).toISOString(),
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

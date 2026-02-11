import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import { reportApi } from '@/api/report'
import type { DailyReportDetail, DailyReportSummary } from '@/api/report'

export interface ReportItem {
  date: string
  totalHeats: number
  normalHeats: number
  abnormalHeats: number
  avgDeviation: number
  pendingTasks: number
  completedTasks: number
  generatedAt: string | null
}

export interface ReportDetail extends ReportItem {
  normalRate: number
  effectiveHours: number
  topDeviations: Array<{ heatNo: string; deviation: number }>
}

function mapSummary(item: DailyReportSummary): ReportItem {
  return {
    date: item.date,
    totalHeats: item.total_heats,
    normalHeats: item.normal_heats,
    abnormalHeats: item.abnormal_heats,
    avgDeviation: item.avg_deviation,
    pendingTasks: item.pending_tasks,
    completedTasks: item.completed_tasks,
    generatedAt: item.generated_at
  }
}

function mapDetail(item: DailyReportDetail): ReportDetail {
  return {
    ...mapSummary(item),
    normalRate: item.normal_rate,
    effectiveHours: item.effective_hours,
    topDeviations: item.top_deviations.map(row => ({ heatNo: row.heat_no, deviation: row.deviation }))
  }
}

function mockReports(): ReportItem[] {
  return Array.from({ length: 7 }).map((_, idx) => {
    const date = dayjs().subtract(idx, 'day').format('YYYY-MM-DD')
    return {
      date,
      totalHeats: 12 + idx,
      normalHeats: 10 + idx,
      abnormalHeats: 2,
      avgDeviation: Number((5.5 + idx * 0.3).toFixed(2)),
      pendingTasks: Math.max(0, 3 - idx),
      completedTasks: 6 + idx,
      generatedAt: `${date}T02:00:00`
    }
  })
}

function mockReportDetail(date: string): ReportDetail {
  const compactDate = date.split('-').join('')
  return {
    date,
    totalHeats: 14,
    normalHeats: 12,
    abnormalHeats: 2,
    avgDeviation: 5.8,
    pendingTasks: 2,
    completedTasks: 8,
    generatedAt: `${date}T02:00:00`,
    normalRate: 85.7,
    effectiveHours: 18.6,
    topDeviations: [
      { heatNo: `H${compactDate}-003`, deviation: 22.4 },
      { heatNo: `H${compactDate}-007`, deviation: 18.1 }
    ]
  }
}

export const useReportStore = defineStore('report', {
  state: () => ({
    list: [] as ReportItem[],
    current: null as ReportDetail | null,
    loading: false
  }),
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const data = await reportApi.list({ page: 1, page_size: 14 })
        this.list = data.items.map(mapSummary)
      } catch (error) {
        console.warn('Report list fallback to mock.', error)
        this.list = mockReports()
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(date: string) {
      this.loading = true
      try {
        const data = await reportApi.get(date)
        this.current = mapDetail(data)
      } catch (error) {
        console.warn('Report detail fallback to mock.', error)
        this.current = mockReportDetail(date)
      } finally {
        this.loading = false
      }
    }
  }
})

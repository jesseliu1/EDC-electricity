import { defineStore } from 'pinia'
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
        console.error('Report list request failed.', error)
        this.list = []
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
        console.error('Report detail request failed.', error)
        this.current = null
      } finally {
        this.loading = false
      }
    }
  }
})
